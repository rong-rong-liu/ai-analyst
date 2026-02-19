#!/usr/bin/env bash
# build-duckdb.sh — Build a local DuckDB database from NovaMart CSV files
#
# Usage:
#   bash scripts/build-duckdb.sh            # Build from CSVs in data/novamart/
#   bash scripts/build-duckdb.sh --help     # Show this help
#
# Creates data/novamart/novamart.duckdb with all tables loaded.
# This is optional — Claude Code can query CSVs directly via DuckDB's
# read_csv() function, but a pre-built .duckdb file is faster for
# repeated queries.

set -euo pipefail

DATA_DIR="data/novamart"
DB_FILE="${DATA_DIR}/novamart.duckdb"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    echo "Usage: bash scripts/build-duckdb.sh [--help]"
    echo ""
    echo "Builds ${DB_FILE} from CSV files in ${DATA_DIR}/"
    echo ""
    echo "Prerequisites:"
    echo "  - Python 3.9+ with duckdb package: pip install duckdb"
    echo "  - OR DuckDB CLI: brew install duckdb (macOS)"
}

# --- Main ---

if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

# Ensure we're in the repo root
if [ ! -f "CLAUDE.md" ]; then
    echo -e "${RED}Error: Run this script from the AI Analyst repo root.${NC}"
    echo "  cd ~/Desktop/ai-analyst && bash scripts/build-duckdb.sh"
    exit 1
fi

# Check for CSV files
if [ ! -d "$DATA_DIR" ] || [ -z "$(ls "$DATA_DIR"/*.csv 2>/dev/null)" ]; then
    echo -e "${RED}Error: No CSV files found in ${DATA_DIR}/${NC}"
    echo ""
    echo "Run the download script first:"
    echo "  bash scripts/download-data.sh"
    exit 1
fi

# Remove existing DB if present
if [ -f "$DB_FILE" ]; then
    echo -e "${YELLOW}Removing existing ${DB_FILE}${NC}"
    rm -f "$DB_FILE"
fi

echo "Building DuckDB database from CSV files..."
echo ""

# Try Python+duckdb first, fall back to DuckDB CLI
if python3 -c "import duckdb" 2>/dev/null; then
    python3 << 'PYEOF'
import duckdb
import os
import glob

data_dir = "data/novamart"
db_file = os.path.join(data_dir, "novamart.duckdb")

con = duckdb.connect(db_file)

csv_files = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
loaded = 0

for csv_path in csv_files:
    table_name = os.path.splitext(os.path.basename(csv_path))[0]
    print(f"  Loading {table_name}...", end="", flush=True)
    con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_csv_auto('{csv_path}')")
    row_count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    print(f" {row_count:,} rows")
    loaded += 1

con.close()
print(f"\nLoaded {loaded} tables into {db_file}")
PYEOF

elif command -v duckdb &> /dev/null; then
    for csv_file in "$DATA_DIR"/*.csv; do
        table_name=$(basename "$csv_file" .csv)
        echo "  Loading ${table_name}..."
        duckdb "$DB_FILE" "CREATE TABLE ${table_name} AS SELECT * FROM read_csv_auto('${csv_file}');"
    done
    echo ""
    echo "Tables loaded into ${DB_FILE}"

else
    echo -e "${RED}Error: Neither Python duckdb package nor DuckDB CLI found.${NC}"
    echo ""
    echo "Install one of:"
    echo "  pip install duckdb          # Python package"
    echo "  brew install duckdb         # macOS CLI"
    echo "  apt install duckdb          # Linux CLI"
    exit 1
fi

# Report file size
if [ -f "$DB_FILE" ]; then
    size=$(ls -lh "$DB_FILE" | awk '{print $5}')
    echo ""
    echo -e "${GREEN}DuckDB database ready: ${DB_FILE} (${size})${NC}"
    echo ""
    echo "Claude Code will automatically use this database for faster queries."
fi
