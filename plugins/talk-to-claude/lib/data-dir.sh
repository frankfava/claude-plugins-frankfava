#!/bin/bash
# Where this plugin may write. Claude Code sets CLAUDE_PLUGIN_DATA inside hooks
# and points it at ~/.claude/plugins/data/<id>/, which survives updates and is
# removed when the plugin is uninstalled. Anything run by hand, such as the mode
# helper, does not get the variable, so fall back to finding the directory.
data_dir() {
  if [[ -n "${CLAUDE_PLUGIN_DATA:-}" ]]; then
    mkdir -p "$CLAUDE_PLUGIN_DATA"; echo "$CLAUDE_PLUGIN_DATA"; return
  fi
  local base="$HOME/.claude/plugins/data"
  for d in "$base"/talk-to-claude-frankfava "$base"/talk-to-claude-*; do
    [[ -d "$d" ]] && { echo "$d"; return; }
  done
  mkdir -p "$base/talk-to-claude-frankfava"; echo "$base/talk-to-claude-frankfava"
}
