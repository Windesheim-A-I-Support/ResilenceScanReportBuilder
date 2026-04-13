#!/usr/bin/env bash
set -euo pipefail

echo "==> Detecting shell profile..."
SHELL_NAME="$(basename "${SHELL:-zsh}")"
if [[ "$SHELL_NAME" == "zsh" ]]; then
  PROFILE="$HOME/.zshrc"
elif [[ "$SHELL_NAME" == "bash" ]]; then
  PROFILE="$HOME/.bash_profile"
else
  PROFILE="$HOME/.profile"
fi
echo "Using profile: $PROFILE"

echo "==> Checking Homebrew..."
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not found. Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

echo "==> Ensuring brew is on PATH for this session..."
if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [[ -x /usr/local/bin/brew ]]; then
  eval "$(/usr/local/bin/brew shellenv)"
else
  echo "Could not find brew after install."
  exit 1
fi

echo "==> Persisting Homebrew PATH..."
if ! grep -q 'brew shellenv' "$PROFILE" 2>/dev/null; then
  if [[ -x /opt/homebrew/bin/brew ]]; then
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$PROFILE"
  else
    echo 'eval "$(/usr/local/bin/brew shellenv)"' >> "$PROFILE"
  fi
fi

echo "==> Installing R and Quarto..."
brew install --cask r-app
brew install --cask quarto

# Optional: uncomment if you also want RStudio
# brew install --cask rstudio

echo "==> Adding R to PATH if needed..."
R_BIN="/Library/Frameworks/R.framework/Resources/bin"
if [[ -d "$R_BIN" ]]; then
  if ! grep -q "$R_BIN" "$PROFILE" 2>/dev/null; then
    echo "export PATH=\"$R_BIN:\$PATH\"" >> "$PROFILE"
  fi
  export PATH="$R_BIN:$PATH"
fi

echo "==> Installing TinyTeX through Quarto..."
quarto install tinytex

echo "==> Adding TinyTeX to PATH..."
TINYTEX_BIN="$HOME/Library/TinyTeX/bin/universal-darwin"
if [[ -d "$TINYTEX_BIN" ]]; then
  if ! grep -q "$TINYTEX_BIN" "$PROFILE" 2>/dev/null; then
    echo "export PATH=\"$TINYTEX_BIN:\$PATH\"" >> "$PROFILE"
  fi
  export PATH="$TINYTEX_BIN:$PATH"
else
  echo "TinyTeX bin folder not found at: $TINYTEX_BIN"
  exit 1
fi

echo "==> Installing useful R packages..."
Rscript -e 'install.packages(c("tinytex","rmarkdown","quarto"), repos="https://cloud.r-project.org")'

echo "==> Verifying installation..."
echo "--- brew ---"
brew --version

echo "--- R ---"
R --version

echo "--- Quarto ---"
quarto --version

echo "--- pdflatex ---"
pdflatex --version | head -n 2

echo "--- tlmgr ---"
tlmgr --version | head -n 2

echo "--- quarto check ---"
quarto check

echo
echo "Done."
echo "Open a new Terminal window or run:"
echo "  source \"$PROFILE\""