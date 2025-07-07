# 🚀 Dotfiles Setup

Automated macOS development environment with 28+ applications and development tools.

## Quick Install

```bash
# Clone repo
git clone https://github.com/yourusername/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
brew bundle install

# Run setup script
chmod +x setup.sh
./setup.sh
```

## What Gets Installed

### Development
- IntelliJ IDEA Ultimate, VS Code, Cursor
- Python 3.13.5, Go 1.23, Node.js, TypeScript
- Docker, Playwright browsers

### Apps
- Chrome, Raycast, Slack, Teams, Discord
- Bitwarden, VeraCrypt, Little Snitch
- Steam, Spotify, Telegram, WhatsApp

### Tools
- Git config, Starship prompt, Tailscale VPN

## Manual Installs (Mac App Store)

```bash
brew install mas
mas install 1160374471  # PiPifier
mas install 899247664   # TestFlight
```

## Set Chrome as Default

```bash
open -a 'Google Chrome' --args --make-default-browser
```

That's it! 🎉