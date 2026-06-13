#!/usr/bin/env bash
set -e

echo "=== Electrolyte MD Toolkit — Setup ==="
echo

# # Python venv #
if [ ! -d "venv" ]; then
    echo "Creating virtual environment"
    python3 -m venv venv
fi

source venv/bin/activate
echo "Using Python: $(python --version) at $(which python)"
echo

# pip dependencies #
echo "Installing Python dependencies"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  Done."
echo

# Packmol check #
if command -v packmol &> /dev/null; then
    echo "Packmol: $(which packmol)"
else
    echo "WARNING: packmol not found on PATH."
    echo "  Install with:  conda install -c conda-forge packmol"
    echo "            or:  sudo apt install packmol"
    echo "  (pack_cell.py needs it)"
fi
echo

# GPU check #
python -c "
import torch
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)} (CUDA {torch.version.cuda})')
else:
    print('GPU: None detected — MD will run on CPU (slow for large systems)')
"
echo

echo "=== Setup complete ==="
echo "Activate the environment with:  source venv/bin/activate"
