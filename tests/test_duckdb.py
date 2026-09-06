import duckdb

conn = duckdb.connect()

print("=== Real Crude Oil Assay Table (DuckDB Analytical Query) ===")
df = conn.execute("""
    SELECT crude_name, origin_country, api_gravity, sulfur_wt_pct, diesel_ago_vol_pct 
    FROM 'data/real_crude_oil_assays.csv' 
    ORDER BY sulfur_wt_pct DESC
""").fetchdf()
print(df.to_string(index=False))

print("\n=== Refinery Equipment Spares Below Reorder Point ===")
df_spares = conn.execute("""
    SELECT part_number, description, oem_manufacturer, stock_on_hand, min_reorder_point, unit_cost_inr, 
           (min_reorder_point - stock_on_hand) * unit_cost_inr AS replenishment_inr 
    FROM 'data/refinery_equipment_spares_catalog.csv' 
    WHERE stock_on_hand < min_reorder_point
""").fetchdf()
print(df_spares.to_string(index=False))
