#!/usr/bin/env bash
#
# Launch script for the Discord bot.
# Usage: ./launch.sh
#
# This script:
#   1. Kills any existing bot process to prevent duplicate responses
#   2. Starts Ollama if not already running (required for chat functionality)
#   3. Launches the bot
#

set -e

# cd to script directory (works even if called from elsewhere)
cd "$(dirname "$0")" || exit 1

# --- Configuration ---
CONDA_ENV="discord-bot"  # Change this to match your conda environment name
OLLAMA_PORT=11434

# --- Activate Conda ---
echo "Activating conda environment ($CONDA_ENV)..."
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    . "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    . "$HOME/anaconda3/etc/profile.d/conda.sh"
elif command -v conda &> /dev/null; then
    eval "$(conda shell.bash hook)"
else
    echo "Conda not found. Please install Conda or activate your environment manually."
    exit 1
fi
conda activate "$CONDA_ENV"

# --- Kill existing bot process ---
EXISTING=$(pgrep -f "python main.py" 2>/dev/null || true)
if [ -n "$EXISTING" ]; then
    echo "Bot already running (PID: $EXISTING). Killing..."
    kill $EXISTING
    sleep 1
    echo "Killed old bot process"
fi

# --- Start Ollama if needed ---
echo "Checking if Ollama is running..."
if curl -s "http://localhost:${OLLAMA_PORT}/api/version" > /dev/null 2>&1; then
    echo "Ollama is already running on port ${OLLAMA_PORT}."
else
    echo "Ollama is not running. Starting it now..."
    pkill -f "ollama serve" 2>/dev/null || true
    sleep 1
    ollama serve &
    echo "Waiting for Ollama to start..."
    sleep 5

    if curl -s "http://localhost:${OLLAMA_PORT}/api/version" > /dev/null 2>&1; then
        echo "Ollama started successfully."
    else
        echo "️Warning: Could not verify Ollama is running. Chat features may not work."
    fi
fi

# --- Launch the bot ---
echo "Starting bot..."
python main.py "$@"
