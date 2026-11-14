eval "$(starship init zsh)"

[[ -o interactive ]] && [[ -s "/Users/python-qa/.gvm/scripts/gvm" ]] && source "/Users/python-qa/.gvm/scripts/gvm"
eval "$(zoxide init zsh)"

export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
export PATH=$PATH:/usr/local/go/bin
autoload -Uz compinit && compinit

# Private env (API keys, tokens): not in git. File mode 600.
[ -f "$HOME/.zshrc.secrets" ] && . "$HOME/.zshrc.secrets"

fpath=(/usr/local/share/zsh-completions $fpath)

. "$HOME/.local/bin/env"
export PATH="/opt/homebrew/opt/ruby/bin:/opt/homebrew/lib/ruby/gems/3.4.0/bin:$PATH"
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"

# bun completions
[ -s "/Users/python-qa/.bun/_bun" ] && source "/Users/python-qa/.bun/_bun"

# bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
