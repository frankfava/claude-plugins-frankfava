# talk-to-claude — plugin

Restart Claude Code after install, update, enable or disable.

## Validate

```bash
claude plugin validate /Users/ffava/DEV/projects/packages/claude-plugins-frankfava
```

```bash
claude plugin validate /Users/ffava/DEV/projects/packages/claude-plugins-frankfava/plugins/talk-to-claude
```

## Install

```bash
claude plugin marketplace add /Users/ffava/DEV/projects/packages/claude-plugins-frankfava
```

```bash
claude plugin install talk-to-claude@frankfava
```

## Update

Bump `version` in `.claude-plugin/plugin.json` first. The update is version-gated: without a bump it reports "already at the latest version" and keeps the old copy, edits and all.

```bash
claude plugin marketplace update frankfava && claude plugin update talk-to-claude@frankfava
```

## Disable / enable

```bash
claude plugin disable talk-to-claude@frankfava
```

```bash
claude plugin enable talk-to-claude@frankfava
```

## Remove

```bash
claude plugin uninstall talk-to-claude@frankfava
```

```bash
claude plugin marketplace remove frankfava
```

Removing the marketplace takes every plugin in it. The cached copy under `~/.claude/plugins/cache/frankfava/talk-to-claude/` survives either way — delete it by hand.
