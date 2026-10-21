"""A deterministic structured-data worker; it deliberately has no LLM.

Handles CSV/TSV/XLSX ingestion into DuckDB tables and executes read-only SQL
so the supervisor can get exact computed answers (sums, averages, group-bys)
instead of approximate vector-search results.
"""

from __future__ import annotations  # Allows modern type hints on supported Python versions.

import hashlib  # Produces a stable content fingerprint for duplicate detection.
import math
import os  # Reads deployment configuration from environment variables.
import re  # Sanitizes filenames/sheet names into safe SQL identifiers, and parses SQL for table validation.
import uuid  # Creates unique file identifiers.
from dataclasses import dataclass  # Gives configuration a small typed container.
from pathlib import Path  # Handles platform-safe filesystem paths.
from typing import Any  # Documents flexible API payload types.

import duckdb  # Embedded analytical database — runs real SQL locally, no server.
import pandas as pd  # Reads CSV/XLSX files before loading them into DuckDB tables.

CSV_SUFFIXES = {".csv", ".tsv"}  # File extensions read via pandas.read_csv.
EXCEL_SUFFIXES = {".xlsx", ".xls"}  # File extensions read via pandas.read_excel (can hold multiple sheets).
TABULAR_SUFFIXES = CSV_SUFFIXES | EXCEL_SUFFIXES  # Every extension this worker accepts.

_IDENTIFIER_SAFE = re.compile(r"[^0-9a-zA-Z_]")  # Matches any character not allowed in a SQL identifier.
_TABLE_REF_PATTERN = re.compile(
    r'(?:FROM|JOIN)\s+"?([A-Za-z_][A-Za-z0-9_]*)"?', re.IGNORECASE
)  # Finds table names referenced after FROM/JOIN, quoted or not.
_CTE_NAME_PATTERN = re.compile(
    r'(?:WITH|,)\s*([A-Za-z_][A-Za-z0-9_]*)\s+AS\s*\(', re.IGNORECASE
)  # Finds CTE aliases so they aren't mistaken for missing real tables.


def clean_for_json(val: Any) -> Any:
    """Recursively replaces NaN, Inf, and -Inf with None, and unwraps numpy scalars for RFC 7159 compliance."""
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    elif isinstance(val, dict):
        return {k: clean_for_json(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple)):
        return [clean_for_json(v) for v in val]
    elif hasattr(val, "item"):
        try:
            return clean_for_json(val.item())
        except Exception:
            return val
    return val


@dataclass(frozen=True)  # Makes accidental configuration mutation impossible.
class AnalysisSettings:
    """Runtime settings, all controllable without code changes."""

    data_dir: Path = Path(os.getenv("DATA_DIR", "./data"))  # Directory for the DuckDB database file.
    db_filename: str = "analysis.duckdb"  # Name of the persistent DuckDB database file.
    max_result_rows: int = 1000  # Hard cap on rows returned from any single query call.


class DuplicateFileError(RuntimeError):  # Raised only when identical content already exists under any name.
    pass


class UnsupportedFileError(RuntimeError):  # Raised when a non-tabular file is handed to this worker.
    pass


class UnsafeQueryError(RuntimeError):  # Raised when the supplied SQL is not a read-only SELECT/CTE statement.
    pass


class DataAnalysisWorker:
    """Ingests structured files as SQL tables and answers computational queries; it never generates an answer."""

    def __init__(self, settings: AnalysisSettings | None = None) -> None:
        self.settings = settings or AnalysisSettings()  # Uses supplied settings or safe environment defaults.
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)  # Creates local state directory if needed.
        self.db_path = self.settings.data_dir / self.settings.db_filename  # Chooses the DuckDB file location.
        try:
            self.conn = duckdb.connect(str(self.db_path))  # Opens (or creates) the persistent local database.
            self._initialize_registry()  # Creates the bookkeeping tables before any ingestion occurs.
        except duckdb.IOException:
            try:
                self.conn = duckdb.connect(str(self.db_path), read_only=True)  # Fallback to read-only when server holds lock.
            except duckdb.IOException:
                self.conn = duckdb.connect(":memory:")  # Resilient fallback on Windows when another process holds an exclusive lock.
                self._initialize_registry()
                self._auto_seed_data_dir()

    def _auto_seed_data_dir(self) -> None:
        """Seeds tables from CSV files in data_dir if database is empty."""
        for csv_path in sorted(self.settings.data_dir.glob("*.csv")):
            try:
                self.ingest(csv_path)
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Registry: dedup + table bookkeeping (stored inside DuckDB itself)
    # ------------------------------------------------------------------ #

    def _initialize_registry(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _files (
                id VARCHAR PRIMARY KEY,
                source_name VARCHAR NOT NULL UNIQUE,
                sha256 VARCHAR NOT NULL UNIQUE,
                media_type VARCHAR,
                created_at TIMESTAMP DEFAULT current_timestamp
            )
            """
        )  # Tracks one row per ingested file, mirroring the RAG worker's SQLite registry pattern.
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _file_tables (
                file_id VARCHAR NOT NULL,
                table_name VARCHAR NOT NULL,
                sheet_name VARCHAR,
                row_count BIGINT NOT NULL,
                column_count INTEGER NOT NULL
            )
            """
        )  # Tracks which physical DuckDB tables belong to which ingested file (an Excel file can create several).

    @staticmethod
    def _sha256(file_path: Path) -> str:
        digest = hashlib.sha256()  # Initializes streaming SHA-256 state.
        with file_path.open("rb") as stream:  # Reads binary content without loading huge files entirely.
            for block in iter(lambda: stream.read(1024 * 1024), b""):  # Processes one MiB at a time.
                digest.update(block)  # Adds each block to the same fingerprint.
        return digest.hexdigest()  # Returns canonical lower-case duplicate key.

    @staticmethod
    def _safe_identifier(name: str) -> str:
        cleaned = _IDENTIFIER_SAFE.sub("_", name).strip("_")  # Replaces anything unsafe for a SQL name with "_".
        if not cleaned:  # Guards against a name that becomes empty after cleaning (e.g. all-symbol input).
            cleaned = "table"
        if cleaned[0].isdigit():  # SQL identifiers cannot start with a digit.
            cleaned = f"t_{cleaned}"
        return cleaned.lower()  # Lower-cases for consistency across the registry.

    @staticmethod
    def _sanitize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Rewrites column headers into safe, predictable SQL identifiers.

        Raw headers like "Units Sold" or "Unit Price" survive straight through
        pandas untouched, but the planning LLM never sees the real headers — it
        guesses conventional snake_case names when writing SQL (e.g. units_sold).
        Normalizing headers at ingest time means the LLM's natural guess is far
        more likely to already be correct, and duplicate column names (which can
        appear after normalization, e.g. two headers that both reduce to "date")
        are disambiguated with a numeric suffix so no data is silently dropped.
        """
        seen: dict[str, int] = {}
        new_columns: list[str] = []
        for col in df.columns:
            cleaned = DataAnalysisWorker._safe_identifier(str(col))
            if cleaned in seen:
                seen[cleaned] += 1
                cleaned = f"{cleaned}_{seen[cleaned]}"
            else:
                seen[cleaned] = 0
            new_columns.append(cleaned)
        df.columns = new_columns
        return df

    def _drop_file_tables(self, file_id: str) -> None:
        rows = self.conn.execute(
            "SELECT table_name FROM _file_tables WHERE file_id = ?", [file_id]
        ).fetchall()  # Finds every physical table this file previously created.
        for (table_name,) in rows:  # A single Excel file can map to several sheet tables.
            self.conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')  # Removes the stale table.
        self.conn.execute("DELETE FROM _file_tables WHERE file_id = ?", [file_id])  # Clears table registry rows.
        self.conn.execute("DELETE FROM _files WHERE id = ?", [file_id])  # Clears the file registry row.

    # ------------------------------------------------------------------ #
    # Ingestion
    # ------------------------------------------------------------------ #

    def _load_dataframes(self, path: Path) -> dict[str, pd.DataFrame]:
        suffix = path.suffix.lower()  # Drives which pandas reader and table-naming scheme applies.
        base_name = self._safe_identifier(path.stem)  # Turns the filename (without extension) into a table prefix.
        if suffix in CSV_SUFFIXES:
            separator = "\t" if suffix == ".tsv" else ","  # Picks the delimiter by extension.
            df = pd.read_csv(path, sep=separator)  # Lets pandas infer real dtypes so SUM/AVG work correctly.
            df = self._sanitize_columns(df)  # Normalizes headers so LLM-guessed column names line up.
            return {base_name: df}  # A CSV always produces exactly one table.
        if suffix in EXCEL_SUFFIXES:
            sheets = pd.read_excel(path, sheet_name=None)  # Reads every sheet, dtypes inferred per column.
            return {
                f"{base_name}__{self._safe_identifier(sheet_name)}": self._sanitize_columns(df)  # Normalizes headers too.
                for sheet_name, df in sheets.items()
                if not df.empty  # Skips sheets with headers but no data rows.
            }
        raise UnsupportedFileError(
            f"{path.name}: this worker only ingests {sorted(TABULAR_SUFFIXES)}, "
            "route other formats to the document retrieval worker instead."
        )  # Makes the boundary between the two workers explicit rather than silently mishandling the file.

    def ingest(self, file_path: str | Path, media_type: str | None = None) -> dict[str, Any]:
        path = Path(file_path).resolve()  # Canonicalizes the caller's supplied local path.
        if not path.is_file():  # Stops early before hashing/loading errors become confusing.
            raise FileNotFoundError(f"Not a readable file: {path}")
        source_name = path.name  # Uses the basename as the user-visible identity.
        file_hash = self._sha256(path)  # Calculates content identity before expensive work.

        hash_match = self.conn.execute(
            "SELECT source_name FROM _files WHERE sha256 = ?", [file_hash]
        ).fetchone()  # Checks whether this exact content is already loaded, regardless of filename.
        if hash_match:
            raise DuplicateFileError(f"Identical content already loaded as {hash_match[0]}")

        name_match = self.conn.execute(
            "SELECT id FROM _files WHERE source_name = ?", [source_name]
        ).fetchone()  # Same filename but different content means this is an updated version of a known file.
        if name_match:
            self._drop_file_tables(name_match[0])  # Removes the stale tables/registry rows before reloading.

        dataframes = self._load_dataframes(path)  # Reads the file into one or more pandas dataframes.
        if not dataframes:  # An Excel workbook where every sheet was empty, for example.
            raise RuntimeError(f"No data rows found in {source_name}")

        file_id = str(uuid.uuid4())  # Creates a stable record id for this one ingestion.
        table_infos: list[dict[str, Any]] = []  # Collects per-table metadata to return to the caller.
        try:
            for table_name, df in dataframes.items():  # Loads every sheet/CSV as its own physical DuckDB table.
                self.conn.register("_incoming_df", df)  # Makes the pandas dataframe visible to SQL temporarily.
                self.conn.execute(f'CREATE OR REPLACE TABLE "{table_name}" AS SELECT * FROM _incoming_df')  # Persists it.
                self.conn.unregister("_incoming_df")  # Cleans up the temporary view immediately after use.
                self.conn.execute(
                    "INSERT INTO _file_tables VALUES (?, ?, ?, ?, ?)",
                    [file_id, table_name, table_name.split("__", 1)[-1] if "__" in table_name else None,
                     len(df), len(df.columns)],
                )  # Records this physical table against the parent file for later lookup/cleanup.
                table_infos.append({"table_name": table_name, "row_count": len(df), "columns": list(df.columns)})

            self.conn.execute(
                "INSERT INTO _files VALUES (?, ?, ?, ?, current_timestamp)",
                [file_id, source_name, file_hash, media_type],
            )  # Commits the file-level registry row only after every table loaded successfully.
        except Exception:  # Keeps the database consistent if any sheet/table fails partway through the loop.
            for table_name in [info["table_name"] for info in table_infos]:  # Cleans up whatever did get created.
                self.conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            self.conn.execute("DELETE FROM _file_tables WHERE file_id = ?", [file_id])  # Removes partial rows.
            self.conn.execute("DELETE FROM _files WHERE id = ?", [file_id])  # Removes the file row if it exists.
            raise  # Preserves the original meaningful exception for the supervisor/API.

        return {
            "file_id": file_id,
            "source_name": source_name,
            "tables": table_infos,
            "updated": bool(name_match),  # Tells the caller whether this replaced a prior version.
        }

    # ------------------------------------------------------------------ #
    # Analysis
    # ------------------------------------------------------------------ #

    def list_tables(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT f.source_name, t.table_name, t.sheet_name, t.row_count, t.column_count
            FROM _file_tables t JOIN _files f ON f.id = t.file_id
            ORDER BY f.created_at
            """
        ).fetchall()  # Joins the two registry tables into one human-readable inventory.
        columns = ["source_name", "table_name", "sheet_name", "row_count", "column_count"]
        return [dict(zip(columns, row)) for row in rows]  # Converts raw tuples into supervisor-friendly dicts.

    def schema(self, table_name: str) -> dict[str, Any]:
        exists = self.conn.execute(
            "SELECT 1 FROM _file_tables WHERE table_name = ?", [table_name]
        ).fetchone()  # Refuses to describe a table this worker didn't create itself.
        if not exists:
            raise ValueError(f"Unknown table: {table_name}")
        info = self.conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()  # Column name/type/nullability.
        row_count = self.conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]  # Exact row count.
        sample = clean_for_json(self.conn.execute(f'SELECT * FROM "{table_name}" LIMIT 5').fetchdf().to_dict(orient="records"))
        return {
            "table_name": table_name,
            "columns": [{"name": row[1], "type": row[2]} for row in info],  # PRAGMA columns: cid, name, type, ...
            "row_count": row_count,
            "sample_rows": sample,  # A few real rows so the supervisor can see actual values, not just types.
        }

    def describe(self, table_name: str) -> list[dict[str, Any]]:
        exists = self.conn.execute(
            "SELECT 1 FROM _file_tables WHERE table_name = ?", [table_name]
        ).fetchone()  # Same ownership check as schema(), before running SUMMARIZE.
        if not exists:
            raise ValueError(f"Unknown table: {table_name}")
        records = self.conn.execute(f'SUMMARIZE "{table_name}"').fetchdf().to_dict(orient="records")
        return clean_for_json(records)
        # DuckDB's built-in SUMMARIZE returns min/max/avg/std/null-count/approx-unique per column in one call.

    @staticmethod
    def _is_read_only(sql: str) -> bool:
        first_word = sql.strip().split(None, 1)[0].upper() if sql.strip() else ""  # Grabs the leading keyword.
        return first_word in {"SELECT", "WITH"}  # Only allows queries that read data, never mutate/define it.

    @staticmethod
    def _has_stacked_statements(sql: str) -> bool:
        trimmed = sql.strip()  # Removes surrounding whitespace before checking for a trailing semicolon.
        inner = trimmed[:-1] if trimmed.endswith(";") else trimmed  # Allows exactly one harmless trailing ";".
        return ";" in inner  # Any semicolon left inside the body means a second statement is being smuggled in.

    def _known_table_names(self) -> set[str]:
        return {
            row[0].lower() for row in self.conn.execute("SELECT table_name FROM _file_tables").fetchall()
        }  # The real, physically-ingested table names — never guessed by an LLM.

    def _validate_referenced_tables(self, sql: str) -> None:
        """Raises a clear, actionable error if the SQL references a table that was never ingested.

        The supervisor's SQL-generating LLM occasionally hallucinates a plausible
        table name (e.g. "production_data") instead of using the real ingested
        name (e.g. "production__q1"). Without this check, that mistake surfaces
        as a raw duckdb.CatalogException deep in fetchdf(), which is unhelpful
        both to a human debugging it and to an LLM trying to self-correct. This
        check fails fast with the real table list attached to the error instead.
        """
        known_tables = self._known_table_names()  # Ground truth: what actually exists.
        referenced = {match.lower() for match in _TABLE_REF_PATTERN.findall(sql)}  # What the SQL asks for.
        cte_names = {match.lower() for match in _CTE_NAME_PATTERN.findall(sql)}  # CTE aliases aren't real tables.
        unknown = referenced - known_tables - cte_names  # Anything left over doesn't exist.
        if unknown:
            available = sorted(known_tables) or ["<no tables ingested yet>"]
            raise ValueError(
                f"Unknown table(s) referenced: {sorted(unknown)}. "
                f"Available tables: {available}. "
                "Call list_tables() to get exact table names before writing SQL."
            )

    def query(self, sql: str) -> dict[str, Any]:
        if not self._is_read_only(sql):  # Blocks DROP/DELETE/UPDATE/INSERT/ATTACH etc. outright.
            raise UnsafeQueryError("Only SELECT/WITH read queries are permitted through this worker.")
        if self._has_stacked_statements(sql):  # Blocks "SELECT 1; DROP TABLE ..."-style statement stacking.
            raise UnsafeQueryError("Only a single SQL statement is permitted per call.")
        self._validate_referenced_tables(sql)  # Fails fast with the real table list instead of a raw DuckDB error.
        result_df = self.conn.execute(sql).fetchdf()  # Executes the supervisor-generated SQL and materializes it.
        truncated = len(result_df) > self.settings.max_result_rows  # Flags whether the caller needs to know more exists.
        if truncated:
            result_df = result_df.head(self.settings.max_result_rows)  # Caps the payload size sent back upstream.
        return {
            "columns": list(result_df.columns),
            "rows": clean_for_json(result_df.to_dict(orient="records")),  # A list of {column: value} dicts, JSON-friendly.
            "row_count_returned": len(result_df),
            "truncated": truncated,  # Tells the supervisor the true result set was larger than what's included.
        }