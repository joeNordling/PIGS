#!/bin/bash
# Launcher script for Flip 7 multiplayer server
#
# Usage:
#   ./flip_7/launch_multiplayer.sh           # play mode  (LAN IP, no reload)
#   ./flip_7/launch_multiplayer.sh --dev     # dev mode   (localhost, auto-reload)
#
# Requires: environment activated with multiplayer extras installed.
#   pip install -e ".[multiplayer]"

# Colour codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🎴 Flip 7 Multiplayer${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check uvicorn is available in the current environment.
if ! python -c "import uvicorn" &> /dev/null; then
    echo -e "${RED}Error: uvicorn is not installed in the current environment.${NC}"
    echo -e "${YELLOW}Run:  pip install -e \".[multiplayer]\"${NC}"
    echo ""
    exit 1
fi

# Check fastapi is available.
if ! python -c "import fastapi" &> /dev/null; then
    echo -e "${RED}Error: fastapi is not installed in the current environment.${NC}"
    echo -e "${YELLOW}Run:  pip install -e \".[multiplayer]\"${NC}"
    echo ""
    exit 1
fi

cd "$PROJECT_ROOT"

# Forward all arguments (e.g. --dev, --host, --port) to the Python launcher.
python -m flip_7.network.launch_server "$@"