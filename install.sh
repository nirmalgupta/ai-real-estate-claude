#!/usr/bin/env bash
# Install the v2 AI Real Estate skill into ~/.claude/.
#
# v2 is pipeline-driven: deterministic Python data layer + Claude
# narrative drafting. Most of the code lives in this repo; only the
# skill markdown gets copied into ~/.claude/skills/. The Python
# pipeline runs from this repo's working directory.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${HOME}/.claude"

echo ""
echo "  AI Real Estate Analyst v2 — pipeline-driven"
echo "  Deterministic data layer + Claude narrative."
echo ""

mkdir -p "${CLAUDE_DIR}/skills"
mkdir -p "${CLAUDE_DIR}/scripts"

# --- Skills (markdown only) ---
echo "Installing skills..."
for d in "${SCRIPT_DIR}/skills/"*/; do
    [ -d "${d}" ] || continue
    name="$(basename "${d}")"
    cp -R "${d%/}" "${CLAUDE_DIR}/skills/"
    echo "  + ${name}"
done

# --- Auxiliary scripts (PDF + iMessage) — only if they exist ---
if [ -d "${SCRIPT_DIR}/scripts" ]; then
    echo ""
    echo "Installing scripts..."
    for f in "${SCRIPT_DIR}/scripts/"*.py; do
        [ -f "${f}" ] || continue
        name="$(basename "${f}")"
        cp "${f}" "${CLAUDE_DIR}/scripts/"
        chmod +x "${CLAUDE_DIR}/scripts/${name}"
        echo "  + ${name}"
    done
fi

# --- Python deps ---
if command -v python3 >/dev/null 2>&1; then
    echo ""
    echo "Checking Python dependencies..."
    deps_to_install=()
    for mod in httpx reportlab; do
        if python3 -c "import ${mod}" 2>/dev/null; then
            echo "  + ${mod} (already installed)"
        else
            deps_to_install+=("${mod}")
        fi
    done
    if [ ${#deps_to_install[@]} -gt 0 ]; then
        echo "  Installing missing: ${deps_to_install[*]}"
        if python3 -m pip install --quiet --user "${deps_to_install[@]}" 2>/dev/null; then
            echo "  ok"
        elif python3 -m pip install --quiet --user --break-system-packages \
            "${deps_to_install[@]}" 2>/dev/null; then
            echo "  ok (used --break-system-packages)"
        else
            echo "  ! Could not install. Run manually:"
            echo "    pip3 install --break-system-packages ${deps_to_install[*]}"
        fi
    fi
fi

# --- Unified setup: API keys + delivery channels ---
# install_config.py walks every optional service one-by-one, lets you
# skip any of them, and silently preserves what you've already configured
# on subsequent runs. Per the project's open-source philosophy: configure
# once here, never prompted at runtime.
echo ""
echo "Setting up optional services (re-run install.sh to add more later)..."
if command -v python3 >/dev/null 2>&1; then
    python3 "${SCRIPT_DIR}/scripts/install_config.py" || {
        echo "  ! install_config.py failed; you can re-run it later:"
        echo "      python3 ${SCRIPT_DIR}/scripts/install_config.py"
    }
else
    echo "  python3 not found — skipping optional-service setup."
fi

echo ""
echo "Done. Restart Claude Code, then try:"
echo ""
echo "  cd ${SCRIPT_DIR}"
echo "  /real-estate 31 Glenleigh Pl, Spring, TX 77381"
echo ""
echo "(The pipeline runs from this repo's working directory — Python"
echo " modules are imported via 'python3 -m pipeline.<...>'.)"
echo ""
