#!/bin/bash
# -*- coding: utf-8 -*-
set -e

echo "System: Installing system dependencies..."
sudo apt update
sudo apt install -y \
    python3-gi \
    gir1.2-gexiv2-0.10 \
    libgexiv2-dev \
    mediainfo \
    python3-dev \
    python3-pip \
    python3-venv

echo "Python: Creating Python virtual environment with system packages..."
python3 -m venv venv --system-site-packages

echo "Activation: Activating virtual environment..."
source venv/bin/activate

echo "Packages: Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Verification: Checking GExiv2 availability in virtual environment..."
if python3 -c "import gi; gi.require_version('GExiv2', '0.10'); from gi.repository import GExiv2" &> /dev/null; then
    echo "OK: GExiv2 module is available."
else
    echo "ERROR: GExiv2 NOT available in venv. Try: sudo apt install python3-gi gir1.2-gexiv2-0.10"
    exit 1
fi

echo "Bootstrap complete! Environment is ready."
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "Then run setup.sh to complete the installation:"
echo "  ./setup.sh"