#!/usr/bin/env bash
# download-data.sh — Download NovaMart Tier 2 data files from GitHub Releases
#
# Usage:
#   bash scripts/download-data.sh            # Downloads sample data (~15MB)
#   bash scripts/download-data.sh --full     # Downloads full dataset (~200MB compressed)
#   bash scripts/download-data.sh --help     # Show this help
#
# The repo ships with Tier 1 data (8 small reference tables, ~4MB).
# This script downloads Tier 2 data (5 large tables: events, sessions,
# orders, users, support_tickets) required for full analysis.

set -euo pipefail

REPO="ai-analyst-lab/ai-analyst"
VERSION="v1.0.0"
DATA_DIR="data/novamart"
CHECKSUM_FILE="data/checksums.sha256"

SAMPLE_ASSET="novamart-sample.tar.gz"
FULL_ASSET="novamart-full.tar.gz"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: bash scripts/download-data.sh [--sample|--full|--help]"
    echo ""
    echo "Options:"
    echo "  --sample   Download 10K-row sample data (~15MB) [default]"
    echo "  --full     Download complete dataset (~200MB compressed, ~690MB uncompressed)"
    echo "  --help     Show this help message"
    echo ""
    echo "Downloaded files are placed in ${DATA_DIR}/"
}

check_prerequisites() {
    if ! command -v curl &> /dev/null; then
        echo -e "${RED}Error: curl is required but not installed.${NC}"
        exit 1
    fi

    if ! command -v shasum &> /dev/null && ! command -v sha256sum &> /dev/null; then
        echo -e "${YELLOW}Warning: Neither shasum nor sha256sum found. Skipping checksum verification.${NC}"
        SKIP_CHECKSUM=true
    else
        SKIP_CHECKSUM=false
    fi
}

verify_checksum() {
    local file="$1"
    local expected_hash="$2"

    if [ "$SKIP_CHECKSUM" = true ]; then
        echo -e "${YELLOW}  Skipping checksum (no sha tool available)${NC}"
        return 0
    fi

    local actual_hash
    if command -v sha256sum &> /dev/null; then
        actual_hash=$(sha256sum "$file" | awk '{print $1}')
    else
        actual_hash=$(shasum -a 256 "$file" | awk '{print $1}')
    fi

    if [ "$actual_hash" = "$expected_hash" ]; then
        echo -e "${GREEN}  Checksum verified${NC}"
        return 0
    else
        echo -e "${RED}  Checksum mismatch!${NC}"
        echo "  Expected: $expected_hash"
        echo "  Got:      $actual_hash"
        return 1
    fi
}

download_asset() {
    local asset_name="$1"
    local url="https://github.com/${REPO}/releases/download/${VERSION}/${asset_name}"

    echo "Downloading ${asset_name} from GitHub Releases..."
    echo "  URL: ${url}"

    local temp_file
    temp_file=$(mktemp)

    if ! curl -fSL --progress-bar -o "$temp_file" "$url"; then
        echo -e "${RED}Error: Download failed.${NC}"
        echo ""
        echo "Possible causes:"
        echo "  - No internet connection"
        echo "  - Release ${VERSION} does not exist yet"
        echo "  - Asset ${asset_name} not found in release"
        echo ""
        echo "Check: https://github.com/${REPO}/releases"
        rm -f "$temp_file"
        exit 1
    fi

    # Verify checksum if available
    if [ -f "$CHECKSUM_FILE" ]; then
        local expected_hash
        expected_hash=$(grep "${asset_name}" "$CHECKSUM_FILE" | awk '{print $1}' || true)
        if [ -n "$expected_hash" ]; then
            verify_checksum "$temp_file" "$expected_hash" || {
                rm -f "$temp_file"
                exit 1
            }
        fi
    fi

    # Extract
    echo "Extracting to ${DATA_DIR}/..."
    mkdir -p "$DATA_DIR"
    tar -xzf "$temp_file" -C "$DATA_DIR"
    rm -f "$temp_file"

    echo -e "${GREEN}Done.${NC}"
}

list_files() {
    echo ""
    echo "Files in ${DATA_DIR}/:"
    echo ""
    if command -v numfmt &> /dev/null; then
        ls -lS "$DATA_DIR"/*.csv 2>/dev/null | awk '{printf "  %-35s %s\n", $NF, $5}' || true
    else
        ls -lhS "$DATA_DIR"/*.csv 2>/dev/null | awk '{printf "  %-35s %s\n", $NF, $5}' || true
    fi
    echo ""
    local count
    count=$(ls "$DATA_DIR"/*.csv 2>/dev/null | wc -l | tr -d ' ')
    echo "Total CSV files: ${count}"
}

# --- Main ---

MODE="sample"

while [[ $# -gt 0 ]]; do
    case $1 in
        --sample)
            MODE="sample"
            shift
            ;;
        --full)
            MODE="full"
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

# Ensure we're in the repo root
if [ ! -f "CLAUDE.md" ]; then
    echo -e "${RED}Error: Run this script from the AI Analyst repo root.${NC}"
    echo "  cd ~/Desktop/ai-analyst && bash scripts/download-data.sh"
    exit 1
fi

check_prerequisites

if [ "$MODE" = "full" ]; then
    echo "=== Downloading full NovaMart dataset ==="
    echo "This will download ~200MB (compressed) / ~690MB (uncompressed)"
    download_asset "$FULL_ASSET"
else
    echo "=== Downloading NovaMart sample data ==="
    echo "This will download ~15MB (10K-row subsets of large tables)"
    download_asset "$SAMPLE_ASSET"
fi

list_files

echo ""
echo -e "${GREEN}Data download complete.${NC}"
echo ""
echo "Next steps:"
echo "  1. (Optional) Build DuckDB: bash scripts/build-duckdb.sh"
echo "  2. Start Claude Code: claude"
echo "  3. Try a query: \"What's our conversion rate by device?\""
