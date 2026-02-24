#!/bin/bash
# setup_linux.sh — installs R, Quarto, TinyTeX and required R packages.
# Called by postinst.sh in the background so dpkg lock is not held.
# Can also be run manually: sudo /opt/ResilenceScanReportBuilder/setup_linux.sh

set -e

export DEBIAN_FRONTEND=noninteractive
export TZ=UTC

QUARTO_VERSION="1.6.39"
INSTALL_DIR="/opt/ResilenceScanReportBuilder"
R_LIB="$INSTALL_DIR/r-library"

log() { echo "[SETUP] $1"; }

# ── R ────────────────────────────────────────────────────────────────────────
if ! command -v Rscript &>/dev/null; then
    log "Installing R from CRAN APT repository..."
    apt-get update -qq
    apt-get install -y --no-install-recommends software-properties-common dirmngr
    # Add CRAN signing key and repository
    wget -qO- https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc \
        | gpg --dearmor -o /usr/share/keyrings/cran.gpg
    UBUNTU_CODENAME=$(. /etc/os-release && echo "$UBUNTU_CODENAME")
    echo "deb [signed-by=/usr/share/keyrings/cran.gpg] https://cloud.r-project.org/bin/linux/ubuntu ${UBUNTU_CODENAME:-jammy}-cran40/" \
        > /etc/apt/sources.list.d/cran.list
    apt-get update -qq
    apt-get install -y --no-install-recommends r-base r-base-dev
else
    log "R already present — skipping."
fi

# ── System libraries required by R packages ───────────────────────────────────
# kableExtra → systemfonts (libharfbuzz-dev, libfribidi-dev)
# rmarkdown  → xml2 (libxml2-dev)
# curl       → libcurl4-openssl-dev
log "Installing system libraries for R packages..."
apt-get install -y --no-install-recommends \
    libharfbuzz-dev libfribidi-dev \
    libxml2-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    libfontconfig1-dev

# ── Quarto ───────────────────────────────────────────────────────────────────
if ! command -v quarto &>/dev/null; then
    log "Downloading Quarto $QUARTO_VERSION..."
    TMP=$(mktemp -d)
    wget -q -O "$TMP/quarto.deb" \
        "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-amd64.deb"
    dpkg -i "$TMP/quarto.deb" || true
    apt-get install -f -y     # fix any missing dependencies
    rm -rf "$TMP"
else
    log "Quarto already present — skipping."
fi

# ── TinyTeX ──────────────────────────────────────────────────────────────────
if ! command -v tlmgr &>/dev/null; then
    log "Installing TinyTeX via Quarto..."
    quarto install tinytex --no-prompt
    # Symlink TinyTeX binaries into /usr/local/bin so they are on PATH for all users.
    # quarto install tinytex installs to ~/.TinyTeX; use $HOME so it works for any user.
    TINYTEX_DIR="${HOME}/.TinyTeX/bin/x86_64-linux"
    if [ -d "$TINYTEX_DIR" ]; then
        log "Symlinking TinyTeX binaries from $TINYTEX_DIR to /usr/local/bin"
        for bin in tlmgr pdflatex xelatex lualatex luatex tex latex; do
            [ -e "$TINYTEX_DIR/$bin" ] && ln -sf "$TINYTEX_DIR/$bin" "/usr/local/bin/$bin" || true
        done
    else
        log "WARNING: TinyTeX dir not found at $TINYTEX_DIR"
    fi
else
    log "TinyTeX already present — skipping."
fi

# ── R packages ───────────────────────────────────────────────────────────────
log "Installing R packages into $R_LIB..."
mkdir -p "$R_LIB"
Rscript -e "
  pkgs <- c(
    'readr', 'dplyr', 'stringr', 'tidyr', 'ggplot2', 'knitr',
    'fmsb', 'scales', 'viridis', 'patchwork', 'RColorBrewer',
    'gridExtra', 'png', 'lubridate', 'kableExtra', 'rmarkdown',
    'jsonlite', 'ggrepel', 'cowplot'
  )
  install.packages(pkgs, lib='$R_LIB', repos='https://cloud.r-project.org', quiet=TRUE)
"
# Ensure the R library is readable by all users
chmod -R a+rX "$R_LIB"

log "Dependency setup complete."
