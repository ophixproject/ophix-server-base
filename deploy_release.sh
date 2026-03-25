#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Ophix Project Server — release deployment script
#
# Usage: ./deploy_release.sh <version>
# Example: ./deploy_release.sh 2026.03.23.01
#
# Run as the service user (e.g. websites) from the releases directory.
# The releases directory should contain:
#   source/          — uploaded release tarballs
#   current -> ...   — symlink to the active release
#
# This script:
#   1. Extracts the release tarball
#   2. Creates a virtualenv and installs packages from requirements.txt
#   3. Runs Django migrate and collectstatic
#   4. Updates the 'current' symlink
#   5. Prints the restart instruction
# =============================================================================

# ---------------------------------------------------------------------------
# Project configuration — edit once per server deployment
# ---------------------------------------------------------------------------
APP_NAME="${APP_NAME:-ophix}"           # systemd service name
VENV_NAME="${VENV_NAME:-.venv}"         # virtualenv directory name
TARBALL_PREFIX="${TARBALL_PREFIX:-release}"  # tar.gz filename prefix

BASE_DIR="/home/websites/${APP_NAME}"
RELEASES_DIR="${BASE_DIR}/releases"
SOURCE_DIR="${RELEASES_DIR}/source"
CURRENT_LINK="current"

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 2026.03.23.01"
    exit 1
fi

VERSION="$1"
RELEASE_DIR="${TARBALL_PREFIX}-${VERSION}"
TARBALL="${SOURCE_DIR}/${RELEASE_DIR}.tar.gz"

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------
if [[ ! -f "${TARBALL}" ]]; then
    echo "ERROR: Tarball not found: ${TARBALL}"
    exit 1
fi

if [[ -d "${RELEASES_DIR}/${RELEASE_DIR}" ]]; then
    echo "ERROR: Release directory already exists: ${RELEASE_DIR}"
    exit 1
fi

echo "Deploying ${APP_NAME} version ${VERSION}"
echo "----------------------------------------"

cd "${RELEASES_DIR}"

# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------
echo "Extracting ${TARBALL}..."
tar -xzf "${TARBALL}"
cd "${RELEASE_DIR}"

# ---------------------------------------------------------------------------
# Virtualenv + dependencies
# ---------------------------------------------------------------------------
echo "Creating virtualenv (${VENV_NAME})..."
python3 -m venv "${VENV_NAME}"
source "${VENV_NAME}/bin/activate"

pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo "Dependencies installed."

# ---------------------------------------------------------------------------
# Django management steps
# ---------------------------------------------------------------------------
echo "Running migrate..."
ophix-manage migrate --noinput

echo "Running collectstatic..."
ophix-manage collectstatic --noinput --clear

# ---------------------------------------------------------------------------
# Optional: sync documentation into DB
# ---------------------------------------------------------------------------
if ophix-manage help ophix_docs_update &>/dev/null; then
    echo "Syncing documentation..."
    ophix-manage ophix_docs_update --include-app-docs ophix_creds,ophix_docs,opthix_theme_tools
fi

# ---------------------------------------------------------------------------
# Update current symlink
# ---------------------------------------------------------------------------
cd "${RELEASES_DIR}"
ln -sfn "${RELEASE_DIR}" "${CURRENT_LINK}"

echo "----------------------------------------"
echo "${APP_NAME} ${VERSION} deployed successfully"
echo "current -> ${RELEASE_DIR}"
echo ""
echo "Restart the service:"
echo "  sudo systemctl restart ${APP_NAME}"
