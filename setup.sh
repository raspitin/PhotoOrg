#!/usr/bin/env bash
set -euo pipefail

# Check if virtual environment exists
if [ ! -d venv ]; then
    echo "??  Virtual environment not found. Please run bootstrap.sh first."
    exit 1
fi

echo "?? Activating virtual environment..."
source venv/bin/activate

echo "?? Installing/updating Python dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

echo "?? Verifying all dependencies..."
python3 -c "
import yaml
import pymediainfo
import tqdm
from gi.repository import GExiv2
print('? All dependencies successfully imported')
"

echo ""
echo "? Setup completed!"
echo ""
echo "To run the application:"
echo "  1. Activate the virtual environment (if not already active):"
echo "     source venv/bin/activate"
echo "  2. Run the program:"
echo "     python3 PhotoOrg.py"
echo ""
echo "Optional: Configure your paths in config.yaml before running."