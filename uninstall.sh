#!/usr/bin/env bash
# Remove v2 AI Real Estate skill from ~/.claude/.
#
# Auto-discovers what to remove from this repo's skills/ and scripts/
# trees. Stays correct as files get added or renamed.
#
# Flags:
#   --dry-run     show what would be removed, don't touch anything
#   --keep-config preserve ~/.claude/re_complete_config.json
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${HOME}/.claude"
CONFIG_FILE="${CLAUDE_DIR}/re_complete_config.json"

DRY_RUN=0
KEEP_CONFIG=0
for arg in "$@"; do
    case "${arg}" in
        --dry-run) DRY_RUN=1 ;;
        --keep-config) KEEP_CONFIG=1 ;;
        -h|--help)
            sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Unknown flag: ${arg}" >&2
            exit 2
            ;;
    esac
done

removed=0
missing=0

remove_path() {
    local target="$1"
    local label="$2"
    if [ -e "${target}" ]; then
        if [ "${DRY_RUN}" -eq 1 ]; then
            echo "  would remove: ${label}"
        else
            rm -rf "${target}"
            echo "  removed: ${label}"
        fi
        removed=$((removed + 1))
    else
        echo "  not found: ${label}"
        missing=$((missing + 1))
    fi
}

echo ""
[ "${DRY_RUN}" -eq 1 ] && echo "  Uninstall (DRY RUN — nothing will be deleted)" \
                       || echo "  AI Real Estate Analyst v2 — Uninstall"
echo ""

echo "Skills:"
if [ -d "${SCRIPT_DIR}/skills" ]; then
    for d in "${SCRIPT_DIR}/skills/"*/; do
        [ -d "${d}" ] || continue
        name="$(basename "${d}")"
        remove_path "${CLAUDE_DIR}/skills/${name}" "skills/${name}"
    done
fi

echo ""
echo "Scripts:"
if [ -d "${SCRIPT_DIR}/scripts" ]; then
    for f in "${SCRIPT_DIR}/scripts/"*.py; do
        [ -f "${f}" ] || continue
        name="$(basename "${f}")"
        remove_path "${CLAUDE_DIR}/scripts/${name}" "scripts/${name}"
    done
fi

echo ""
echo "User config:"
if [ "${KEEP_CONFIG}" -eq 1 ]; then
    if [ -f "${CONFIG_FILE}" ]; then
        echo "  preserved: re_complete_config.json (--keep-config)"
    fi
else
    if [ -f "${CONFIG_FILE}" ]; then
        handle="$(python3 -c "import json,sys; print(json.load(open('${CONFIG_FILE}')).get('imessage_to',''))" 2>/dev/null || echo "")"
        [ -n "${handle}" ] && echo "  (saved iMessage handle was: ${handle})"
    fi
    remove_path "${CONFIG_FILE}" "re_complete_config.json"
fi

echo ""
[ "${DRY_RUN}" -eq 1 ] \
    && echo "Dry run complete. ${removed} would be removed, ${missing} not present." \
    || echo "Done. ${removed} removed, ${missing} not present."
[ "${DRY_RUN}" -eq 0 ] && echo "Restart Claude Code so it picks up the change."
echo "(Python deps not removed: pip uninstall httpx reportlab if you want.)"
echo ""
