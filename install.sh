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

# --- Optional: HUD FMR API key ---
echo ""
echo "Optional: HUD Fair Market Rent API key (for rent benchmarks)"
echo "  Get a free key at https://www.huduser.gov/hudapi/"
if [ -z "${HUD_API_KEY:-}" ]; then
    echo "  Then add to your shell profile:"
    echo "    export HUD_API_KEY=<your key>"
else
    echo "  HUD_API_KEY is already set in your environment."
fi

# --- Optional: iMessage recipient config ---
CONFIG_FILE="${CLAUDE_DIR}/re_complete_config.json"
echo ""
echo "Optional: iMessage delivery (for Phase F send-to-phone)"
if [ -f "${CONFIG_FILE}" ] && grep -q '"imessage_to"' "${CONFIG_FILE}" 2>/dev/null; then
    handle="$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['imessage_to'])" 2>/dev/null || echo "")"
    echo "  Already configured: ${handle}"
else
    echo "  Phone number (e.g. +15551234567) or Apple ID email, or leave blank to skip:"
    read -r -p "  iMessage handle: " IMSG_HANDLE
    if [ -n "${IMSG_HANDLE}" ]; then
        printf '{"imessage_to": "%s"}\n' "${IMSG_HANDLE}" > "${CONFIG_FILE}"
        chmod 600 "${CONFIG_FILE}"
        echo "  + saved to ${CONFIG_FILE}"
    else
        echo "  - skipped"
    fi
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
