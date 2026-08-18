# frankfava

Claude Code plugins by Frank Fava. One entry per plugin under `plugins/`.

## Plugins

| Plugin | What it does | Plugin docs |
|---|---|---|

## Install

```bash
claude plugin marketplace add frankfava/claude-plugins-frankfava
```

Restart Claude Code afterwards. Hooks load at startup and MCP servers connect at session start, so a running session will not pick up a new plugin.

To work on it locally, add the directory instead of the repo:

```bash
claude plugin marketplace add /path/to/claude-plugins-frankfava
```

## Adding a plugin

Create `plugins/<name>/.claude-plugin/plugin.json`, then add an entry to `.claude-plugin/marketplace.json`:

```json
{ "name": "<name>", "description": "...", "source": "./plugins/<name>" }
```

Local sources must sit **under this directory**. `../elsewhere` and absolute paths are both rejected by `claude plugin validate`. A plugin that lives in another repo has to come in as a git source instead:

```json
{ "name": "<name>", "source": { "source": "github", "repo": "owner/repo" } }
```

Validate before installing:

```bash
claude plugin validate .
```

Updates are version-gated. Bump `version` in the plugin's `plugin.json` first, or `claude plugin update` will report you are already current and keep the old copy.
