#!/bin/bash
# Setup script for Flip 7 conda environment
# Usage: source flip_7/setup_env.sh

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Flip 7 Environment Setup${NC}"
echo -e "${BLUE}========================================${NC}"

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

ENV_NAME="pigs-flip7"

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo -e "${YELLOW}Warning: conda not found. Please install Anaconda or Miniconda.${NC}"
    return 1
fi

# Check if environment already exists
if conda env list | grep -q "^${ENV_NAME} "; then
    echo -e "${GREEN}Environment '${ENV_NAME}' already exists.${NC}"
    echo -e "${BLUE}Activating environment...${NC}"
    conda activate ${ENV_NAME}
else
    echo -e "${BLUE}Creating conda environment '${ENV_NAME}'...${NC}"
    echo -e "${BLUE}This may take a few minutes...${NC}"

    # Create environment from yml file
    conda env create -f "${SCRIPT_DIR}/environment.yml"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Environment created successfully!${NC}"
        echo -e "${BLUE}Activating environment...${NC}"
        conda activate ${ENV_NAME}

        # Install the package in development mode
        echo -e "${BLUE}Installing flip7 package in development mode...${NC}"
        cd "$PROJECT_ROOT"
        pip install -e .

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}Package installed successfully!${NC}"
        else
            echo -e "${YELLOW}Warning: Package installation had issues. You may need to run 'pip install -e .' manually.${NC}"
        fi
    else
        echo -e "${YELLOW}Failed to create environment.${NC}"
        return 1
    fi
fi

# Verify installation
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Environment Status${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Environment: ${GREEN}${ENV_NAME}${NC}"
echo -e "Python version: ${GREEN}$(python --version)${NC}"
echo -e "Working directory: ${GREEN}${PROJECT_ROOT}${NC}"

echo ""
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo -e "${BLUE}Quick Start:${NC}"
echo -e "  Run tests:    ${GREEN}pytest flip_7/tests/ -v${NC}"
echo -e "  With coverage: ${GREEN}pytest flip_7/tests/ --cov=flip_7 --cov-report=term-missing${NC}"
echo -e "  Deactivate:   ${GREEN}conda deactivate${NC}"
echo ""
echo -e "${BLUE}To activate this environment later:${NC}"
echo -e "  ${GREEN}conda activate ${ENV_NAME}${NC}"
echo -e "${BLUE}To update the environment:${NC}"
echo -e "  ${GREEN}conda env update -f flip_7/environment.yml --prune${NC}"
echo ""
