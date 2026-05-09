#!/usr/bin/env bash
# Install AI Real Estate Analyst skills into ~/.claude/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${HOME}/.claude"

echo ""
echo "  AI Real Estate Analyst — Claude Code Skills"
echo "  7 skills · 5 parallel agents · 4 Python scripts"
echo ""

mkdir -p "${CLAUDE_DIR}/skills"
mkdir -p "${CLAUDE_DIR}/agents"
mkdir -p "${CLAUDE_DIR}/scripts"

echo "Installing orchestrator skill..."
cp -R "${SCRIPT_DIR}/real-estate" "${CLAUDE_DIR}/skills/"
echo "  + real-estate (orchestrator)"

echo ""
echo "Installing sub-skills..."
for d in "${SCRIPT_DIR}/skills/"*/; do
    name="$(basename "${d}")"
    cp -R "${d}" "${CLAUDE_DIR}/skills/"
    echo "  + ${name}"
done

echo ""
echo "Installing agents..."
for f in "${SCRIPT_DIR}/agents/"*.md; do
    name="$(basename "${f}")"
    cp "${f}" "${CLAUDE_DIR}/agents/"
    echo "  + ${name%.md}"
done

echo ""
echo "Installing scripts..."
for f in "${SCRIPT_DIR}/scripts/"*.py; do
    name="$(basename "${f}")"
    cp "${f}" "${CLAUDE_DIR}/scripts/"
    chmod +x "${CLAUDE_DIR}/scripts/${name}"
    echo "  + ${name}"
done

# Optional: install Python deps for PDF
if command -v python3 >/dev/null 2>&1; then
    echo ""
    echo "Installing Python deps for PDF generation (optional)..."

    # Already installed?
    if python3 -c "import reportlab" 2>/dev/null; then
        echo "  + reportlab (already installed)"
    # Try the polite install first
    elif python3 -m pip install --quiet --user reportlab 2>/dev/null; then
        echo "  + reportlab"
    # macOS Python 3.12+ requires --break-system-packages for system pip
    elif python3 -m pip install --quiet --user --break-system-packages reportlab 2>/dev/null; then
        echo "  + reportlab (used --break-system-packages)"
    else
        echo "  ! Could not install reportlab automatically."
        echo "    PDF generation will fail until you run one of these:"
        echo "      pip3 install --break-system-packages reportlab"
        echo "      python3 -m venv ~/.claude/venv && ~/.claude/venv/bin/pip install reportlab"
    fi
fi

# iMessage recipient config (for /real-estate-complete)
CONFIG_FILE="${CLAUDE_DIR}/re_complete_config.json"
echo ""
echo "iMessage send config (for /real-estate-complete)..."
if [ -f "${CONFIG_FILE}" ] && grep -q '"imessage_to"' "${CONFIG_FILE}" 2>/dev/null; then
    existing="$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['imessage_to'])" 2>/dev/null || echo '')"
    echo "  Already configured: ${existing}"
    echo "  (Edit ${CONFIG_FILE} to change.)"
else
    echo "  /real-estate-complete sends the report to your phone via iMessage."
    echo "  Enter your iMessage handle (phone like +15551234567 or Apple ID email)."
    echo "  Press Enter to skip — you can configure later."
    read -r -p "  iMessage handle: " IMSG_HANDLE
    if [ -n "${IMSG_HANDLE}" ]; then
        printf '{"imessage_to": "%s"}\n' "${IMSG_HANDLE}" > "${CONFIG_FILE}"
        chmod 600 "${CONFIG_FILE}"
        echo "  + saved to ${CONFIG_FILE}"
    else
        echo "  - skipped. /real-estate-complete will save the PDF without sending."
        echo "    To configure later:  echo '{\"imessage_to\": \"+15551234567\"}' > ${CONFIG_FILE}"
    fi
fi

echo ""
echo "Done. Restart Claude Code, then try:"
echo ""
echo "  /real-estate-analyze 1234 Main St, Austin, TX 78701"
echo "  /real-estate-complete 1234 Main St, Austin, TX 78701   # full pipeline + iMessage"
echo ""
