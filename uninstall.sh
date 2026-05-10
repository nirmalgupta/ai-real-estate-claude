#!/usr/bin/env bash
# Remove AI Real Estate Analyst skills from ~/.claude/
#
# Auto-discovers what to remove by iterating THIS repo's tree:
#   real-estate/         -> ${CLAUDE_DIR}/skills/real-estate
#   skills/<name>/       -> ${CLAUDE_DIR}/skills/<name>
#   agents/<name>.md     -> ${CLAUDE_DIR}/agents/<name>.md
#   scripts/<name>.py    -> ${CLAUDE_DIR}/scripts/<name>.py
#   re_complete_config.json (user iMessage handle)
#
# Flags:
#   --dry-run     show what would be removed, don't touch anything
#   --keep-config preserve ${CLAUDE_DIR}/re_complete_config.json
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
            sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Unknown flag: ${arg}" >&2
            echo "Try: $0 --help" >&2
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
if [ "${DRY_RUN}" -eq 1 ]; then
    echo "  AI Real Estate Analyst — Uninstall (DRY RUN, nothing will be deleted)"
else
    echo "  AI Real Estate Analyst — Uninstall"
fi
echo ""

# 1. Orchestrator skill (real-estate/)
echo "Skills (orchestrator):"
if [ -d "${SCRIPT_DIR}/real-estate" ]; then
    remove_path "${CLAUDE_DIR}/skills/real-estate" "skills/real-estate"
fi

# 2. Sub-skills (skills/<name>/)
echo ""
echo "Skills (sub-skills):"
if [ -d "${SCRIPT_DIR}/skills" ]; then
    for d in "${SCRIPT_DIR}/skills/"*/; do
        [ -d "${d}" ] || continue
        name="$(basename "${d}")"
        remove_path "${CLAUDE_DIR}/skills/${name}" "skills/${name}"
    done
fi

# 3. Agents
echo ""
echo "Agents:"
if [ -d "${SCRIPT_DIR}/agents" ]; then
    for f in "${SCRIPT_DIR}/agents/"*.md; do
        [ -f "${f}" ] || continue
        name="$(basename "${f}")"
        remove_path "${CLAUDE_DIR}/agents/${name}" "agents/${name}"
    done
fi

# 4. Scripts
echo ""
echo "Scripts:"
if [ -d "${SCRIPT_DIR}/scripts" ]; then
    for f in "${SCRIPT_DIR}/scripts/"*.py; do
        [ -f "${f}" ] || continue
        name="$(basename "${f}")"
        remove_path "${CLAUDE_DIR}/scripts/${name}" "scripts/${name}"
    done
fi

# 5. Per-user iMessage config
echo ""
echo "User config:"
if [ "${KEEP_CONFIG}" -eq 1 ]; then
    if [ -f "${CONFIG_FILE}" ]; then
        echo "  preserved: re_complete_config.json (--keep-config)"
    else
        echo "  not found: re_complete_config.json"
    fi
else
    if [ -f "${CONFIG_FILE}" ]; then
        # Surface the handle before deleting so user can recreate later
        handle="$(python3 -c "import json,sys; print(json.load(open('${CONFIG_FILE}')).get('imessage_to',''))" 2>/dev/null || echo "")"
        if [ -n "${handle}" ]; then
            echo "  (saved iMessage handle was: ${handle})"
        fi
    fi
    remove_path "${CONFIG_FILE}" "re_complete_config.json"
fi

echo ""
if [ "${DRY_RUN}" -eq 1 ]; then
    echo "Dry run complete. ${removed} item(s) would be removed, ${missing} not present."
    echo "Re-run without --dry-run to actually uninstall."
else
    echo "Done. ${removed} item(s) removed, ${missing} not present."
    echo "Restart Claude Code so it picks up the change."
    echo "(reportlab Python package not removed — pip uninstall reportlab if you want.)"
fi
echo ""
