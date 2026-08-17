#!/bin/bash
# Installation script for Linux/Mac

echo "======================================"
echo "Facebook Comment Monitor - Installer"
echo "======================================"
echo ""

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.12.0"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Error: Python 3.12+ required. Found: $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION detected"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to create virtual environment"
    exit 1
fi

echo "✅ Virtual environment created"
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to install dependencies"
    exit 1
fi

echo "✅ Dependencies installed"
echo ""

# Install Playwright browsers
echo "Installing Playwright browsers..."
playwright install chromium

if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to install Playwright browsers"
    exit 1
fi

echo "✅ Playwright browsers installed"
echo ""

# Setup configuration
if [ ! -f "config.yaml" ]; then
    echo "Creating configuration file..."
    cp config.yaml.example config.yaml
    echo "✅ Configuration file created"
else
    echo "ℹ️  Configuration file already exists"
fi
echo ""

# Create directories
echo "Creating directories..."
mkdir -p session database logs
echo "✅ Directories created"
echo ""

# Success message
echo "======================================"
echo "✅ Installation Complete!"
echo "======================================"
echo ""
echo "To start the application:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run the application: python -m app.main"
echo ""
echo "Or use the quick start script:"
echo "  ./run.sh"
echo ""
echo "For more information, see README.md"
echo ""
