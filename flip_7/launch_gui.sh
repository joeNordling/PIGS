#!/bin/bash
# Launcher script for Flip 7 GUI
# Usage: ./flip_7/launch_gui.sh

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🎴 Flip 7 Game Tracker${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Check if conda environment exists
ENV_NAME="pigs-flip7"

if ! conda env list | grep -q "^${ENV_NAME} "; then
    echo -e "${YELLOW}Environment '${ENV_NAME}' not found.${NC}"
    echo -e "${BLUE}Please run the setup script first:${NC}"
    echo -e "  ${GREEN}source flip_7/setup_env.sh${NC}"
    echo ""
    exit 1
fi

# Activate environment
echo -e "${BLUE}Activating environment '${ENV_NAME}'...${NC}"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate ${ENV_NAME}

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo -e "${YELLOW}Streamlit not found. Installing...${NC}"
    pip install streamlit>=1.28.0
fi

# Change to project root
cd "$PROJECT_ROOT"

# Launch Streamlit
echo -e "${GREEN}Starting Flip 7 GUI...${NC}"
echo ""
echo -e "${BLUE}The GUI will open in your browser at:${NC}"
echo -e "${GREEN}http://localhost:8501${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the application${NC}"
echo ""

streamlit run flip_7/gui/app.py
