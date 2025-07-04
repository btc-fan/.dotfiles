#!/bin/bash

# Dotfiles Setup Script
set -e

echo "🚀 Starting dotfiles setup..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}Installing Homebrew...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo -e "${GREEN}✓ Homebrew already installed${NC}"
fi

# Clean up deprecated taps
echo -e "${YELLOW}Cleaning up deprecated taps...${NC}"
brew untap homebrew/cask-versions 2>/dev/null || true
brew untap homebrew/cask-fonts 2>/dev/null || true
brew untap homebrew/bundle 2>/dev/null || true
echo -e "${GREEN}✓ Deprecated taps cleaned up${NC}"

# Install packages from Brewfile
echo -e "${YELLOW}Installing packages from Brewfile...${NC}"
brew bundle install

# Setup git configuration with stow
echo -e "${YELLOW}Setting up git configuration...${NC}"
if [ -d "git" ]; then
    stow git
    echo -e "${GREEN}✓ Git configuration linked${NC}"
else
    echo -e "${RED}❌ git directory not found. Make sure git/.gitconfig exists${NC}"
fi

# Setup pyenv and install latest Python
echo -e "${YELLOW}Setting up Python with pyenv...${NC}"
if command -v pyenv &> /dev/null; then
    # Add pyenv to PATH for this script
    export PATH="$HOME/.pyenv/bin:$PATH"
    eval "$(pyenv init -)"
    
    # Get latest Python 3.x version
    LATEST_PYTHON=$(pyenv install --list | grep -E "^\s*3\.[0-9]+\.[0-9]+$" | tail -1 | tr -d ' ')
    
    if [ ! -z "$LATEST_PYTHON" ]; then
        echo -e "${YELLOW}Installing Python $LATEST_PYTHON...${NC}"
        pyenv install $LATEST_PYTHON
        pyenv global $LATEST_PYTHON
        
        # Upgrade pip
        pip install --upgrade pip
        echo -e "${GREEN}✓ Python $LATEST_PYTHON installed and set as global${NC}"
    else
        echo -e "${RED}❌ Could not determine latest Python version${NC}"
    fi
else
    echo -e "${RED}❌ pyenv not found${NC}"
fi

# Setup Go with GVM (Go Version Manager)
echo -e "${YELLOW}Setting up Go Version Manager (GVM)...${NC}"
if ! command -v gvm &> /dev/null; then
    # Install GVM
    bash < <(curl -s -S -L https://raw.githubusercontent.com/moovweb/gvm/master/binscripts/gvm-installer)
    
    # Source GVM in current session
    [[ -s "$HOME/.gvm/scripts/gvm" ]] && source "$HOME/.gvm/scripts/gvm"
    
    if command -v gvm &> /dev/null; then
        echo -e "${YELLOW}Installing Go 1.23 with GVM...${NC}"
        gvm install go1.23 -B
        gvm use go1.23 --default
        echo -e "${GREEN}✓ Go 1.23 installed and set as default${NC}"
    else
        echo -e "${RED}❌ GVM installation failed. You may need to restart your terminal and manually install Go 1.23${NC}"
    fi
else
    echo -e "${YELLOW}Installing Go 1.23 with GVM...${NC}"
    gvm install go1.23 -B
    gvm use go1.23 --default
    echo -e "${GREEN}✓ Go 1.23 installed and set as default${NC}"
fi

echo -e "${GREEN}🎉 Setup complete!${NC}"
echo ""
echo "You may need to restart your terminal or run:"
echo "  source ~/.zshrc"
echo ""
echo "Installed versions:"
echo "  Python: $(python --version 2>/dev/null || echo 'Not found')"
echo "  Go: $(go version 2>/dev/null || echo 'Not found')"
echo "  Git: $(git --version 2>/dev/null || echo 'Not found')"
