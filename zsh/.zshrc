eval "$(starship init zsh)"

[[ -s "/Users/python-qa/.gvm/scripts/gvm" ]] && source "/Users/python-qa/.gvm/scripts/gvm"
eval "$(zoxide init zsh)"

export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
export PATH=$PATH:/usr/local/go/bin
autoload -Uz compinit && compinit



