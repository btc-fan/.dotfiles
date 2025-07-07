#!/bin/bash

# Dotfiles Setup Script - Resilient Version
# Continues installation even when individual components fail

echo "🚀 Starting dotfiles setup..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Error tracking
ERRORS=()

# Function to log errors but continue
log_error() {
    ERRORS+=("$1")
    echo -e "${RED}❌ $1${NC}"
}

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}Installing Homebrew...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || log_error "Homebrew installation failed"
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
if ! brew bundle install; then
    log_error "Some Brewfile packages failed to install"
    echo -e "${YELLOW}Continuing with remaining setup...${NC}"
fi

# Setup git configuration with stow
echo -e "${YELLOW}Setting up git configuration...${NC}"
if [ -d "git" ]; then
    if stow git 2>/dev/null; then
        echo -e "${GREEN}✓ Git configuration linked${NC}"
    else
        log_error "Git configuration linking failed"
    fi
else
    log_error "git directory not found. Make sure git/.gitconfig exists"
fi

# Setup all other dotfiles with stow
echo -e "${YELLOW}Setting up additional dotfiles with stow...${NC}"
DOTFILE_DIRS=("zsh" "vim" "tmux" "ssh" "vscode" "scripts")

for dir in "${DOTFILE_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        if stow "$dir" 2>/dev/null; then
            echo -e "${GREEN}✓ $dir configuration linked${NC}"
        else
            log_error "$dir configuration linking failed"
        fi
    else
        echo -e "${YELLOW}⚠ $dir directory not found, skipping...${NC}"
    fi
done

# Setup pyenv and install latest Python
echo -e "${YELLOW}Setting up Python with pyenv...${NC}"
if command -v pyenv &> /dev/null; then
    # Add pyenv to PATH for this script
    export PATH="$HOME/.pyenv/bin:$PATH"
    eval "$(pyenv init -)" 2>/dev/null || true
    
    # Install dependencies for Python compilation (fixes lzma module issue)
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    brew install xz 2>/dev/null || log_error "Failed to install xz dependency"
    
    # Set compiler flags for proper Python compilation
    export LDFLAGS="-L$(brew --prefix xz)/lib $LDFLAGS"
    export CPPFLAGS="-I$(brew --prefix xz)/include $CPPFLAGS"
    export PKG_CONFIG_PATH="$(brew --prefix xz)/lib/pkgconfig:$PKG_CONFIG_PATH"
    
    # Get latest Python 3.x version
    LATEST_PYTHON=$(pyenv install --list 2>/dev/null | grep -E "^\s*3\.[0-9]+\.[0-9]+$" | tail -1 | tr -d ' ')
    
    if [ ! -z "$LATEST_PYTHON" ]; then
        echo -e "${YELLOW}Installing Python $LATEST_PYTHON with proper lzma support...${NC}"
        if pyenv install $LATEST_PYTHON --skip-existing 2>/dev/null; then
            pyenv global $LATEST_PYTHON 2>/dev/null || log_error "Failed to set Python as global"
            
            # Upgrade pip
            pip install --upgrade pip 2>/dev/null || log_error "Failed to upgrade pip"
            echo -e "${GREEN}✓ Python $LATEST_PYTHON installed and set as global${NC}"
        else
            log_error "Python installation failed"
        fi
    else
        log_error "Could not determine latest Python version"
    fi
else
    log_error "pyenv not found"
fi

# Setup Go 1.23 specifically
echo -e "${YELLOW}Setting up Go 1.23...${NC}"

# First install latest Go as bootstrap (if not already installed)
if ! command -v go &> /dev/null; then
    echo -e "${YELLOW}Installing Go via Homebrew as bootstrap...${NC}"
    brew install go 2>/dev/null || log_error "Failed to install Go via Homebrew"
fi

# Set up GVM for version management
echo -e "${YELLOW}Setting up GVM for Go version management...${NC}"
if ! command -v gvm &> /dev/null; then
    # Remove existing GVM if it exists but isn't working
    if [ -d "$HOME/.gvm" ]; then
        echo -e "${YELLOW}Removing existing GVM installation...${NC}"
        rm -rf "$HOME/.gvm"
    fi
    
    # Install GVM
    if bash < <(curl -s -S -L https://raw.githubusercontent.com/moovweb/gvm/master/binscripts/gvm-installer) 2>/dev/null; then
        # Source GVM in current session
        [[ -s "$HOME/.gvm/scripts/gvm" ]] && source "$HOME/.gvm/scripts/gvm"
        echo -e "${GREEN}✓ GVM installed${NC}"
    else
        log_error "GVM installation failed"
    fi
fi

# Use Homebrew Go as bootstrap and install Go 1.23
if command -v gvm &> /dev/null; then
    source "$HOME/.gvm/scripts/gvm" 2>/dev/null || true
    export GOROOT_BOOTSTRAP=$(brew --prefix go)/libexec 2>/dev/null || true
    
    echo -e "${YELLOW}Installing Go 1.23 with GVM...${NC}"
    if gvm install go1.23 2>/dev/null && gvm use go1.23 --default 2>/dev/null; then
        echo -e "${GREEN}✓ Go 1.23 installed and set as default${NC}"
    else
        log_error "GVM Go 1.23 installation failed, using Homebrew Go instead"
        echo -e "${GREEN}✓ Go $(go version 2>/dev/null | awk '{print $3}' || echo 'unknown') available via Homebrew${NC}"
    fi
else
    echo -e "${GREEN}✓ Go $(go version 2>/dev/null | awk '{print $3}' || echo 'unknown') available via Homebrew${NC}"
fi

# Setup Node.js and TypeScript development environment
echo -e "${YELLOW}Setting up Node.js and TypeScript environment...${NC}"
if command -v node &> /dev/null && command -v npm &> /dev/null; then
    echo -e "${GREEN}✓ Node.js $(node --version 2>/dev/null || echo 'unknown') and npm $(npm --version 2>/dev/null || echo 'unknown') installed${NC}"
    
    # Install global TypeScript and Playwright dependencies
    echo -e "${YELLOW}Installing TypeScript and Playwright dependencies...${NC}"
    npm install -g typescript ts-node @types/node 2>/dev/null || log_error "Failed to install TypeScript dependencies"
    npm install -g @playwright/test 2>/dev/null || log_error "Failed to install Playwright"
    
    # Install Playwright browsers
    echo -e "${YELLOW}Installing Playwright browsers...${NC}"
    npx playwright install 2>/dev/null || log_error "Failed to install Playwright browsers"
    npx playwright install-deps 2>/dev/null || log_error "Failed to install Playwright system dependencies"
    
    echo -e "${GREEN}✓ TypeScript and Playwright environment configured${NC}"
else
    log_error "Node.js not found"
fi

# Configure Starship prompt
echo -e "${YELLOW}Configuring Starship prompt...${NC}"
if command -v starship &> /dev/null; then
    # Check if starship is already configured to avoid duplicates
    if ! grep -q "starship init zsh" ~/.zshrc 2>/dev/null; then
        if echo 'eval "$(starship init zsh)"' >> ~/.zshrc 2>/dev/null; then
            echo -e "${GREEN}✓ Starship prompt enabled in ~/.zshrc${NC}"
        else
            log_error "Failed to configure Starship prompt"
        fi
    else
        echo -e "${GREEN}✓ Starship already configured${NC}"
    fi
    
    # Activate starship for current session
    eval "$(starship init zsh)" 2>/dev/null || true
    echo -e "${GREEN}✓ Starship prompt activated${NC}"
else
    log_error "Starship not found"
fi

echo -e "${GREEN}🎉 Setup complete!${NC}"
echo ""

# Show any errors that occurred
if [ ${#ERRORS[@]} -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Some issues occurred during setup:${NC}"
    for error in "${ERRORS[@]}"; do
        echo -e "  ${RED}• $error${NC}"
    done
    echo ""
fi

echo "You may need to restart your terminal or run:"
echo "  source ~/.zshrc"
echo ""
echo "Starship prompt has been enabled. Restart your terminal to see the new prompt."
echo ""
echo "To install Go 1.23 manually (if GVM failed):"
echo "  source ~/.gvm/scripts/gvm"
echo "  export GOROOT_BOOTSTRAP=\$(brew --prefix go)/libexec"
echo "  gvm install go1.23"
echo "  gvm use go1.23 --default"
echo ""
echo "To set Google Chrome as default browser:"
echo "  1. Open System Preferences > General"
echo "  2. Set 'Default web browser' to Google Chrome"
echo "  3. Or use: open -a 'Google Chrome' --args --make-default-browser"
echo ""
echo "To configure Raycast:"
echo "  1. Launch Raycast (⌘ + Space)"
echo "  2. Go to Raycast Settings"
echo "  3. Disable Spotlight if you want Raycast as primary launcher"
echo "  4. System Preferences > Keyboard > Shortcuts > Spotlight > Uncheck 'Show Spotlight search'"
echo ""
echo "Installed versions:"
echo "  Python: $(python --version 2>/dev/null || echo 'Not found')"
echo "  Go: $(go version 2>/dev/null || echo 'Not found')"
echo "  Git: $(git --version 2>/dev/null || echo 'Not found')"
echo "  Node.js: $(node --version 2>/dev/null || echo 'Not found')"
echo "  npm: $(npm --version 2>/dev/null || echo 'Not found')"
echo "  TypeScript: $(tsc --version 2>/dev/null || echo 'Not found')"
echo "  Playwright: $(npx playwright --version 2>/dev/null || echo 'Not found')"