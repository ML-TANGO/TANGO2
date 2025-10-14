#!/bin/bash

# This script sets up the environment for the project.
# It detects the OS and installs Ollama and Python dependencies accordingly.

echo "======================================="
echo "  Project Environment Setup Script   "
echo "======================================="

# Step 1: Detect Operating System
echo "\n[Step 1/3] Checking Operating System..."
OS="$(uname)"

if [ "$OS" == "Darwin" ]; then
    echo "- Detected OS: macOS"
    INSTALL_CMD="curl -fsSL https://ollama.com/install.sh | sh"
elif [ "$OS" == "Linux" ]; then
    echo "- Detected OS: Linux"
    INSTALL_CMD="curl -fsSL https://ollama.com/install.sh | sh"
else
    echo "- Detected OS: Windows or other"
    INSTALL_CMD="manual"
fi

# Step 2: Install Ollama
echo "\n[Step 2/3] Checking and installing Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "- Ollama is not found."
    if [ "$INSTALL_CMD" == "manual" ]; then
        echo "- For Windows, please install Ollama manually."
        echo "  Download from: https://ollama.com/download"
        echo "- After installation, please re-run this script."
    else
        echo "- Installing Ollama..."
        eval $INSTALL_CMD
    fi
else
    echo "- Ollama is already installed."
fi

# Step 3: Install Python requirements
echo "\n[Step 3/3] Checking and installing Python requirements..."
if [ -f "requirements.txt" ]; then
    echo "- requirements.txt found."
    echo "- Installing packages..."
    pip install -r requirements.txt
    echo "- Python packages installed."
else
    echo "- Warning: requirements.txt not found. Skipping Python package installation."
fi

# Step 4: Check and pull the LLM model from config.ini
echo "\n[Step 4/4] Checking and pulling the LLM model..."
MODEL_NAME="gemma3" # Default model
if [ -f "config.ini" ]; then
    # Read MODEL_NAME from config.ini, trim whitespace
    CONFIG_MODEL_NAME=$(grep -E '^[[:space:]]*MODEL_NAME' config.ini | cut -d '=' -f 2 | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    if [ ! -z "$CONFIG_MODEL_NAME" ]; then
        MODEL_NAME=$CONFIG_MODEL_NAME
    fi
fi
echo "- Using model: '$MODEL_NAME' (from config.ini or default)"

if command -v ollama &> /dev/null; then
    if [[ $(ollama list) == *"$MODEL_NAME"* ]]; then
        echo "- Model '$MODEL_NAME' is already available."
    else
        echo "- Model '$MODEL_NAME' not found. Pulling from Ollama..."
        ollama pull "$MODEL_NAME"
    fi
else
    echo "- Ollama is not installed. Skipping model pull."
fi

echo " ======================================="
echo "  Setup Complete!                    "
echo "======================================="
echo "You can now run the main application using: python3 main.py"
