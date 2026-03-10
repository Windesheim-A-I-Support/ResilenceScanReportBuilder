#!/bin/bash
# setup_linux.sh -- installs R, Quarto, TinyTeX and required R packages.
# Called by postinst.sh in the background so dpkg lock is not held.
# Can also be run manually: sudo /opt/ResilenceScanReportBuilder/setup_linux.sh

set -e

export DEBIAN_FRONTEND=noninteractive
export TZ=UTC

QUARTO_VERSION="1.6.39"
INSTALL_DIR="/opt/ResilenceScanReportBuilder"
R_LIB="$INSTALL_DIR/r-library"

log() { echo "[SETUP] $1"; }

# Default to FAIL; overwritten to PASS only when all steps complete cleanly.
SETUP_RESULT="FAIL"

# Write running flag immediately so the app knows setup is in progress.
echo "running" > "$INSTALL_DIR/setup_running.flag"
chmod a+r "$INSTALL_DIR/setup_running.flag" 2>/dev/null || true

# On any exit (normal or error) write the completion flag and notify the user.
_on_exit() {
    echo "$SETUP_RESULT" > "$INSTALL_DIR/setup_complete.flag"
    chmod a+r "$INSTALL_DIR/setup_complete.flag" 2>/dev/null || true
    rm -f "$INSTALL_DIR/setup_running.flag"
    # Best-effort desktop notification for the logged-in user.
    LOGGED_USER=$(logname 2>/dev/null || true)
    if [ -n "$LOGGED_USER" ]; then
        USER_ID=$(id -u "$LOGGED_USER" 2>/dev/null || true)
        if [ -n "$USER_ID" ]; then
            if [ "$SETUP_RESULT" = "PASS" ]; then
                sudo -u "$LOGGED_USER" \
                    DISPLAY=:0 \
                    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$USER_ID/bus" \
                    notify-send "ResilienceScan" "Setup complete. You can now generate reports." \
                    2>/dev/null || true
            else
                sudo -u "$LOGGED_USER" \
                    DISPLAY=:0 \
                    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$USER_ID/bus" \
                    notify-send -u critical "ResilienceScan" "Setup finished with errors. Check /var/log/resilencescan-setup.log" \
                    2>/dev/null || true
            fi
        fi
    fi
}
trap _on_exit EXIT

# -- R ------------------------------------------------------------------------
# Minimum required R major.minor (binary packages exist from this version).
R_MIN_MAJOR=4
R_MIN_MINOR=4

_r_version_ok() {
    # Returns 0 (true) if installed R meets R_MIN_MAJOR.R_MIN_MINOR, else 1.
    local ver major minor
    ver=$(Rscript --version 2>&1 | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "0.0.0")
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    [ "$major" -gt "$R_MIN_MAJOR" ] || \
        ([ "$major" -eq "$R_MIN_MAJOR" ] && [ "$minor" -ge "$R_MIN_MINOR" ])
}

_install_r_cran() {
    apt-get update -qq
    apt-get install -y --no-install-recommends software-properties-common dirmngr
    wget -qO- https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc \
        | gpg --dearmor -o /usr/share/keyrings/cran.gpg
    UBUNTU_CODENAME=$(. /etc/os-release && echo "$UBUNTU_CODENAME")
    echo "deb [signed-by=/usr/share/keyrings/cran.gpg] https://cloud.r-project.org/bin/linux/ubuntu ${UBUNTU_CODENAME:-jammy}-cran40/" \
        > /etc/apt/sources.list.d/cran.list
    apt-get update -qq
    apt-get install -y --no-install-recommends r-base r-base-dev
}

R_UPGRADED=false
if ! command -v Rscript &>/dev/null; then
    log "R not found - installing from CRAN..."
    _install_r_cran
    R_UPGRADED=true
elif ! _r_version_ok; then
    INSTALLED_R=$(Rscript --version 2>&1 | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "unknown")
    log "R $INSTALLED_R found but older than required ${R_MIN_MAJOR}.${R_MIN_MINOR} - upgrading..."
    _install_r_cran
    R_UPGRADED=true
else
    INSTALLED_R=$(Rscript --version 2>&1 | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "unknown")
    log "R $INSTALLED_R already meets requirements (>= ${R_MIN_MAJOR}.${R_MIN_MINOR}) - skipping install."
fi

# -- System libraries required by R packages -----------------------------------
# kableExtra -> systemfonts (libharfbuzz-dev, libfribidi-dev)
# rmarkdown  -> xml2 (libxml2-dev)
# curl       -> libcurl4-openssl-dev
log "Installing system libraries for R packages..."
apt-get install -y --no-install-recommends \
    libharfbuzz-dev libfribidi-dev \
    libxml2-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    libfontconfig1-dev

# -- Quarto -------------------------------------------------------------------
if ! command -v quarto &>/dev/null; then
    log "Downloading Quarto $QUARTO_VERSION..."
    TMP=$(mktemp -d)
    wget -q -O "$TMP/quarto.deb" \
        "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-amd64.deb"
    dpkg -i "$TMP/quarto.deb" || true
    apt-get install -f -y     # fix any missing dependencies
    rm -rf "$TMP"
else
    log "Quarto already present -- skipping."
fi

# -- TinyTeX ------------------------------------------------------------------
if ! command -v tlmgr &>/dev/null; then
    log "Installing TinyTeX via Quarto..."
    quarto install tinytex --no-prompt
    # Symlink TinyTeX binaries into /usr/local/bin so they are on PATH for all users.
    # Quarto 1.4+ installs to ~/.local/share/quarto/tools/tinytex/; older versions
    # used ~/.TinyTeX/.  Check both locations.
    ARCH="$(uname -m)-linux"
    TINYTEX_DIR=""
    for candidate in \
        "${HOME}/.local/share/quarto/tools/tinytex/bin/${ARCH}" \
        "${HOME}/.TinyTeX/bin/${ARCH}" \
        "${HOME}/.TinyTeX/bin/x86_64-linux"; do
        if [ -d "$candidate" ]; then
            TINYTEX_DIR="$candidate"
            break
        fi
    done
    if [ -n "$TINYTEX_DIR" ]; then
        log "Symlinking TinyTeX binaries from $TINYTEX_DIR to /usr/local/bin"
        for bin in tlmgr pdflatex xelatex lualatex luatex tex latex; do
            [ -e "$TINYTEX_DIR/$bin" ] && ln -sf "$TINYTEX_DIR/$bin" "/usr/local/bin/$bin" || true
        done
    else
        log "WARNING: TinyTeX bin dir not found after install - tried ~/.local/share/quarto/tools/tinytex and ~/.TinyTeX"
    fi
else
    log "TinyTeX already present -- skipping."
fi

# -- R packages ---------------------------------------------------------------
log "Installing R packages into $R_LIB..."

# If R was upgraded, wipe the old r-library - binary packages are compiled for
# a specific R minor version and will not load under a different version.
if [ "$R_UPGRADED" = "true" ] && [ -d "$R_LIB" ]; then
    log "R was upgraded - removing stale r-library to force clean package install: $R_LIB"
    rm -rf "$R_LIB"
fi

mkdir -p "$R_LIB"

# Ensure the r-library is writable before attempting package installation.
if ! touch "$R_LIB/_write_test_" 2>/dev/null; then
    log "WARNING: R library not writable - attempting to fix permissions..."
    chmod -R u+w "$R_LIB" 2>/dev/null || true
    chown -R root:root "$R_LIB" 2>/dev/null || true
    if ! touch "$R_LIB/_write_test_" 2>/dev/null; then
        log "ERROR: R library still not writable after chmod/chown. Package install will fail."
        log "  Path: $R_LIB"
    fi
fi
rm -f "$R_LIB/_write_test_"

NCPUS=$(nproc 2>/dev/null || echo 2)
R_PKGS="'readr','dplyr','stringr','tidyr','ggplot2','knitr','fmsb','scales','viridis','patchwork','RColorBrewer','gridExtra','png','lubridate','kableExtra','rmarkdown','jsonlite','ggrepel','cowplot'"

Rscript -e "
  pkgs <- c($R_PKGS)
  install.packages(pkgs, lib='$R_LIB', repos='https://cloud.r-project.org', Ncpus=${NCPUS}, quiet=FALSE)
"

# Verify all packages installed -- install.packages does not exit non-zero on
# partial failure, so check explicitly and retry any that are missing.
log "Verifying R packages..."
MISSING=$(Rscript --no-save -e "
  pkgs <- c($R_PKGS)
  miss <- pkgs[!pkgs %in% rownames(installed.packages(lib.loc='$R_LIB'))]
  cat(paste(miss, collapse=' '))
" 2>/dev/null || true)

if [ -n "$MISSING" ]; then
    log "Retrying missing packages: $MISSING"
    for pkg in $MISSING; do
        Rscript -e "install.packages('$pkg', lib='$R_LIB', repos='https://cloud.r-project.org')" || true
    done
    # Final check after retry
    STILL_MISSING=$(Rscript --no-save -e "
      pkgs <- c($R_PKGS)
      miss <- pkgs[!pkgs %in% rownames(installed.packages(lib.loc='$R_LIB'))]
      cat(paste(miss, collapse=' '))
    " 2>/dev/null || true)
    if [ -n "$STILL_MISSING" ]; then
        log "ERROR: R packages still missing after retry: $STILL_MISSING"
        SETUP_RESULT="FAIL"
    else
        log "R package retry succeeded -- all packages present."
    fi
else
    log "R package verification: all packages present."
fi

# Ensure the R library is readable by all users
chmod -R a+rX "$R_LIB"

SETUP_RESULT="PASS"
log "Dependency setup complete."
