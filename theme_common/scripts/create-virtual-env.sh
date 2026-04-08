#!/bin/bash

# Define the name of the virtual environment
VENV_DIR="venv"

# Check if the virtual environment directory exists
if [ ! -d "$VENV_DIR" ]; then
  # Create the virtual environment
  python3 -m venv $VENV_DIR
  echo "Virtual environment created in $VENV_DIR."
else
  echo "Virtual environment already exists in $VENV_DIR."
fi
