"""
Bounded runtime telemetry storage for DRISHTI-MRPL.

Design goals:
- Keep only a bounded number of records in RAM.
- Keep only a bounded amount of runtime history on disk.
- Keep histories separated by asset.
- Never allow the runtime demo dataset to grow forever.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import threading
from typing import Any

from .risk_engine import RiskAssessment
from .sensors import SensorReading


class RuntimeStore:
    """
    Thread-safe runtime telemetry store.

    RAM:
        Stores only the most recent `max_records_per_asset` samples
        for each asset.

    Disk:
        Stores JSONL records, but automatically removes records older
        than `retention_minutes`.

    This is intentionally lightweight for the prototype.
    """

    def __init__(
        self,
        *,
        max_records_per_asset: int = 300,
        retention_minutes: int = 60,
        storage_path: str | Path | None = None,
        persist: bool = True,
        load_existing: bool = False,
    ) -> None:

        if max_records_per_asset < 10:
            raise ValueError(
                "max_records_per_asset must be at least 10."
            )

        if retention_minutes < 1:
            raise ValueError(
                "retention_minutes must be at least 1."
            )

        self.max_records_per_asset = int(
            max_records_per_asset
        )

        self.retention_minutes = int(
            retention_minutes
        )

        self.storage_path = (
            Path(storage_path)
            if storage_path
            else None
        )

        self.persist = bool(
            persist
            and self.storage_path
        )

        self._lock = threading.RLock()

        # --------------------------------------------------
        # Per-asset hot memory buffer
        # --------------------------------------------------

        self._records: dict[
            str,
            deque[dict[str, Any]]
        ] = defaultdict(
            lambda: deque(
                maxlen=self.max_records_per_asset
            )
        )

        self._last_sequence: int | None = None

        if self.persist:

            assert self.storage_path is not None

            self.storage_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            if load_existing:
                self._load_existing()

    # ======================================================
    # INTERNAL HELPERS
    # ======================================================

    @staticmethod
    def _asset_id(
        record: dict[str, Any]
    ) -> str:

        return str(
            record.get(
                "reading",
                {},
            ).get(
                "asset_id",
                "UNKNOWN",
            )
        )

    @staticmethod
    def _timestamp_to_datetime(
        timestamp: str,
    ) -> datetime | None:

        try:

            return datetime.fromisoformat(
                timestamp.replace(
                    "Z",
                    "+00:00",
                )
            )

        except (
            ValueError,
            TypeError,
        ):

            return None

    def _record_is_recent(
        self,
        record: dict[str, Any],
    ) -> bool:

        timestamp = (
            record.get(
                "reading",
                {},
            ).get(
                "timestamp"
            )
        )

        if not timestamp:
            return False

        record_time = (
            self._timestamp_to_datetime(
                timestamp
            )
        )

        if record_time is None:
            return False

        cutoff = (
            datetime.now(
                timezone.utc
            )
            - timedelta(
                minutes=self.retention_minutes
            )
        )

        return record_time >= cutoff

    # ======================================================
    # LOAD EXISTING HISTORY
    # ======================================================

    def _load_existing(self) -> None:

        """
        Load only recent, valid records from disk.

        Old data is ignored so starting the application does
        not pull a huge historical file back into RAM.
        """

        if (
            not self.storage_path
            or not self.storage_path.exists()
        ):
            return

        try:

            with self.storage_path.open(
                "r",
                encoding="utf-8",
            ) as fh:

                # Read only the last bounded number of lines.
                recent_lines = deque(
                    fh,
                    maxlen=(
                        self.max_records_per_asset
                        * 10
                    ),
                )

            for line in recent_lines:

                try:

                    record = json.loads(
                        line
                    )

                except json.JSONDecodeError:

                    continue

                if not isinstance(
                    record,
                    dict,
                ):
                    continue

                if (
                    "reading"
                    not in record
                    or "risk"
                    not in record
                ):
                    continue

                if not self._record_is_recent(
                    record
                ):
                    continue

                asset_id = self._asset_id(
                    record
                )

                self._records[
                    asset_id
                ].append(record)

                sequence = (
                    record[
                        "reading"
                    ].get(
                        "sequence"
                    )
                )

                if isinstance(
                    sequence,
                    int,
                ):

                    self._last_sequence = (
                        sequence
                    )

        except OSError:

            # History is optional for the simulator.
            return

    # ======================================================
    # APPEND
    # ======================================================

    def append(
        self,
        reading: SensorReading,
        risk: RiskAssessment,
    ) -> dict[str, Any]:

        record = {
            "reading": reading.to_dict(),
            "risk": risk.to_dict(),
        }

        asset_id = (
            reading.asset_id
        )

        with self._lock:

            self._records[
                asset_id
            ].append(record)

            self._last_sequence = (
                reading.sequence
            )

            if (
                self.persist
                and self.storage_path
            ):

                self._append_to_disk(
                    record
                )

                # Occasionally compact the disk file.
                #
                # We don't rewrite the file on every sample
                # because that would create unnecessary I/O.

                if (
                    reading.sequence % 600
                    == 0
                ):

                    self.compact_disk()

        return record

    def _append_to_disk(
        self,
        record: dict[str, Any],
    ) -> None:

        try:

            assert (
                self.storage_path
                is not None
            )

            with self.storage_path.open(
                "a",
                encoding="utf-8",
            ) as fh:

                fh.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        separators=(
                            ",",
                            ":",
                        ),
                    )
                    + "\n"
                )

        except OSError as exc:

            raise RuntimeError(
                "Failed to persist runtime telemetry: "
                f"{exc}"
            ) from exc

    # ======================================================
    # DISK RETENTION
    # ======================================================

    def compact_disk(self) -> None:

        """
        Rewrite the JSONL file keeping only records
        newer than the configured retention period.

        This keeps disk usage bounded.
        """

        if (
            not self.persist
            or not self.storage_path
            or not self.storage_path.exists()
        ):
            return

        cutoff = (
            datetime.now(
                timezone.utc
            )
            - timedelta(
                minutes=self.retention_minutes
            )
        )

        temporary_path = (
            self.storage_path.with_suffix(
                ".tmp"
            )
        )

        try:

            with self.storage_path.open(
                "r",
                encoding="utf-8",
            ) as source, temporary_path.open(
                "w",
                encoding="utf-8",
            ) as destination:

                for line in source:

                    try:

                        record = json.loads(
                            line
                        )

                    except json.JSONDecodeError:

                        continue

                    if not isinstance(
                        record,
                        dict,
                    ):
                        continue

                    timestamp = (
                        record.get(
                            "reading",
                            {},
                        ).get(
                            "timestamp"
                        )
                    )

                    if not timestamp:
                        continue

                    record_time = (
                        self._timestamp_to_datetime(
                            timestamp
                        )
                    )

                    if (
                        record_time is None
                        or record_time < cutoff
                    ):
                        continue

                    destination.write(
                        json.dumps(
                            record,
                            ensure_ascii=False,
                            separators=(
                                ",",
                                ":",
                            ),
                        )
                        + "\n"
                    )

            temporary_path.replace(
                self.storage_path
            )

        except OSError:

            # Don't crash the simulator merely because
            # history compaction failed.
            try:

                if temporary_path.exists():
                    temporary_path.unlink()

            except OSError:
                pass

    # ======================================================
    # RETRIEVAL
    # ======================================================

    def latest(
        self,
        asset_id: str | None = None,
    ) -> dict[str, Any] | None:

        with self._lock:

            if asset_id is not None:

                records = self._records.get(
                    asset_id
                )

                if not records:
                    return None

                return dict(
                    records[-1]
                )

            # Global latest across all assets.
            latest_record = None
            latest_sequence = -1

            for records in self._records.values():

                if not records:
                    continue

                candidate = records[-1]

                sequence = int(
                    candidate[
                        "reading"
                    ].get(
                        "sequence",
                        -1,
                    )
                )

                if sequence > latest_sequence:

                    latest_sequence = (
                        sequence
                    )

                    latest_record = candidate

            return (
                dict(latest_record)
                if latest_record
                else None
            )

    def history(
        self,
        *,
        limit: int = 120,
        asset_id: str | None = None,
    ) -> list[dict[str, Any]]:

        limit = max(
            1,
            min(
                int(limit),
                self.max_records_per_asset,
            ),
        )

        with self._lock:

            if asset_id is not None:

                records = list(
                    self._records.get(
                        asset_id,
                        [],
                    )
                )

                return records[-limit:]

            # Combined recent history.
            combined: list[
                dict[str, Any]
            ] = []

            for records in (
                self._records.values()
            ):

                combined.extend(records)

            combined.sort(
                key=lambda record: int(
                    record[
                        "reading"
                    ].get(
                        "sequence",
                        -1,
                    )
                )
            )

            return combined[-limit:]

    def readings(
        self,
        *,
        limit: int = 120,
        asset_id: str | None = None,
    ) -> list[SensorReading]:

        result: list[
            SensorReading
        ] = []

        for record in self.history(
            limit=limit,
            asset_id=asset_id,
        ):

            try:

                result.append(
                    SensorReading(
                        **record[
                            "reading"
                        ]
                    )
                )

            except (
                TypeError,
                KeyError,
            ):

                continue

        return result

    # ======================================================
    # METADATA
    # ======================================================

    def count(
        self,
        asset_id: str | None = None,
    ) -> int:

        with self._lock:

            if asset_id is not None:

                return len(
                    self._records.get(
                        asset_id,
                        [],
                    )
                )

            return sum(
                len(records)
                for records
                in self._records.values()
            )

    def asset_counts(self) -> dict[str, int]:

        with self._lock:

            return {
                asset_id: len(records)
                for asset_id, records
                in self._records.items()
            }

    def last_sequence(
        self,
    ) -> int | None:

        with self._lock:
            return self._last_sequence

    def clear_memory(self) -> None:

        with self._lock:

            self._records.clear()

            self._last_sequence = None

    def clear_disk(self) -> None:

        """
        Delete generated runtime history.

        Only use this for demonstration-data cleanup.
        """

        with self._lock:

            if (
                self.storage_path
                and self.storage_path.exists()
            ):

                try:

                    self.storage_path.unlink()

                except OSError:
                    pass

    def summary(self) -> dict[str, Any]:

        return {
            "records_in_memory": self.count(),

            "records_per_asset": (
                self.asset_counts()
            ),

            "max_records_per_asset": (
                self.max_records_per_asset
            ),

            "retention_minutes": (
                self.retention_minutes
            ),

            "persistent": self.persist,

            "storage_path": (
                str(self.storage_path)
                if self.storage_path
                else None
            ),
        }