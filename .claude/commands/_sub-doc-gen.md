# [SUBAGENT] Documentation Generator

> **⚠️ SUBAGENT — This command is designed to be called by other agents, not directly by users.**
> Primarily used by `/infra-orchestrate`, `/script-polish`, and `/runbook-gen` to generate or update README files when new scripts or folders are created.

## How to invoke directly
```
/_sub-doc-gen <path-to-folder-or-script>
/_sub-doc-gen <path> --type readme|header|both
```

## How it is called by other agents
```
Run /_sub-doc-gen on <folder> to create or update the README after adding new scripts.
```

---

## Your Task

Generate documentation for: **$ARGUMENTS**

---

## Documentation Types

### Type 1: README.md for a folder

When called on a **folder path**, generate or update the `README.md` for that folder.

**Read the folder contents first.** Inventory all scripts/playbooks present, then generate:

```markdown
# <Platform> / <Subfolder> — <Tool Type>

Brief description of what this folder contains and its purpose.

## Contents

| Script / File | Purpose |
|---------------|---------|
| `script-name.ps1` | <derived from .SYNOPSIS or filename> |
| `playbook-name.yml` | <derived from header comment or task names> |

## Prerequisites

- <Module or collection required>
- <Connection or credential needed>

## Usage

Brief examples of how to run the key scripts in this folder.

```<language>
<example command>
```

## Related
- <Link to parent folder README>
- <Link to CLAUDE.md for this domain>
```

**Rules:**
- If a README already exists, UPDATE it to add new scripts — don't overwrite existing content that's still accurate
- Script purposes should be derived from reading `.SYNOPSIS` blocks or task names — don't make them up
- Keep it concise — this is a navigation aid, not a full manual (the runbook-gen command handles full documentation)

### Type 2: Script header block

When called on a **specific script file**, generate a compliant header block to insert at the top.

Read the script to understand its purpose, then generate:

**For PowerShell:**
```powershell
<#
.SYNOPSIS
    <derived from reading the script>
.DESCRIPTION
    <detailed description>
.PARAMETER <name>
    <for each parameter found in the script>
.EXAMPLE
    .<script-name>.ps1 -Parameter Value
.NOTES
    Author  : humbledgeeks-allen
    Date    : <today's date>
    Version : 1.0
    Module  : <module used in the script>
    Repo    : infra-automation/<path derived from file location>
#>
```

**For Ansible:**
```yaml
---
# =============================================================================
# Playbook : <filename>
# Description : <derived from task names and hosts>
# Author  : humbledgeeks-allen
# Date    : <today's date>
# Collection : <collection used>
# =============================================================================
```

**For Shell:**
```bash
#!/bin/bash
# =============================================================================
# Script  : <filename>
# Description : <derived from reading the script>
# Author  : humbledgeeks-allen
# Date    : <today's date>
# Compat  : <Ubuntu 22.04 bash | Synology DSM ash>
# =============================================================================
set -euo pipefail
```

### Type 3: Both

When `--type both` is specified or both a folder and individual scripts need documentation, run Type 2 on each script that lacks a header, then run Type 1 to generate the folder README.

---

## Output behavior

- **Always show** the generated content in a code block first
- **Ask before writing** — "Shall I save this to `<path>`?" — unless called as a subagent (then write directly)
- If updating an existing README, show a diff of what changed
- If a script header already exists and is compliant, say so and skip it

---

## Return value (when called as subagent)

```
DOC_GEN_RESULT:
files_updated: [list of paths written]
files_skipped: [list of paths already compliant]
status: COMPLETE | PARTIAL | SKIPPED
```
