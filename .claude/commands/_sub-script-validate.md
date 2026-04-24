# [SUBAGENT] Script Standards Validator

> **⚠️ SUBAGENT — This command is designed to be called by other agents, not directly by users.**
> Primarily used by `/health-check`, `/script-polish`, and `/infra-orchestrate` to validate scripts meet repo standards before they are saved or committed.

## How to invoke directly
```
/_sub-script-validate <path-to-script>
/_sub-script-validate <inline-script-content>
```

## How it is called by other agents
```
Run /_sub-script-validate on <script> before saving it. Only proceed if validation passes.
```

---

## Your Task

Validate this script against repo standards: **$ARGUMENTS**

---

## Validation Checklist

### PowerShell Script Validation (`.ps1`)

Run every check. Mark each as PASS ✅, FAIL ❌, or WARN ⚠️.

| Check | Criteria | Result |
|-------|----------|--------|
| Header present | File starts with `<#` block | |
| .SYNOPSIS present | Non-empty `.SYNOPSIS` line | |
| .DESCRIPTION present | Non-empty `.DESCRIPTION` block | |
| .NOTES present | Contains Author, Date, Version | |
| Author field | `Author  : humbledgeeks-allen` | |
| Date field | `Date    : YYYY-MM-DD` format | |
| Version field | `Version : 1.0` or higher | |
| Module documented | `Module  :` field present | |
| Repo path documented | `Repo    :` field present | |
| No hardcoded credentials | No plaintext passwords/tokens | |
| Credential handling | Uses Get-Credential, $env:, or SecureString | |
| Error handling | $ErrorActionPreference or try/catch present | |
| Validation block | Script ends with status check commands | |
| No Write-Host for credentials | Passwords not logged to console | |
| Naming convention | `Verb-Noun.ps1` format | |

### Ansible Playbook Validation (`.yml` / `.yaml`)

| Check | Criteria | Result |
|-------|----------|--------|
| Header comment block | `# ===` or `# Playbook:` block at top | |
| Description in header | Non-empty description | |
| Author in header | `humbledgeeks-allen` | |
| Date in header | Date field present | |
| Collection documented | `# Collection:` in header | |
| No plaintext passwords | No `password:` with hardcoded values | |
| Vault variables used | Credentials use `{{ vault_` prefix | |
| Validation task | Final task checks/confirms success | |
| `become` used appropriately | Not used unnecessarily | |
| `validate_certs` documented | If false, comment explains why | |

### Shell Script Validation (`.sh`)

| Check | Criteria | Result |
|-------|----------|--------|
| Shebang present | `#!/bin/bash` or `#!/bin/sh` | |
| Header comment block | `# ====` or `# Script:` block at top | |
| Author documented | Author line in header | |
| `set -euo pipefail` | Present in bash scripts | |
| No hardcoded credentials | No plaintext passwords | |
| Input validation | Script validates required parameters | |

---

## Scoring

Calculate an overall score:
- Each PASS = 1 point
- Each WARN = 0.5 points
- Each FAIL = 0 points
- Score = (points / total checks) × 10

Score thresholds:
- 9–10: **APPROVED** — meets standards
- 7–8.9: **APPROVED WITH WARNINGS** — minor issues, acceptable
- 5–6.9: **NEEDS WORK** — significant gaps, recommend `/script-polish` before committing
- Below 5: **BLOCKED** — do not commit; run `/script-polish` first

---

## Output format

```
## Script Validation Report
File: <path>
Type: PowerShell | Ansible | Shell
Checks run: <count>
Score: <X>/10

### Results
✅ PASS: <check name>
❌ FAIL: <check name> — <specific issue>
⚠️ WARN: <check name> — <specific issue>

### Verdict: APPROVED | APPROVED WITH WARNINGS | NEEDS WORK | BLOCKED

### Recommended actions:
- <specific fix for each FAIL>
```

---

## Return value (when called as subagent)

```
SCRIPT_VALIDATE_RESULT:
status: APPROVED | APPROVED_WITH_WARNINGS | NEEDS_WORK | BLOCKED
score: <float 0-10>
fail_count: <number>
warn_count: <number>
blocking: true | false
recommendations: [list of specific fixes]
```

If `blocking: true`, the calling agent should not save or commit the script until issues are resolved.
