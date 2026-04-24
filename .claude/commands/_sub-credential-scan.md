# [SUBAGENT] Credential Scanner

> **⚠️ SUBAGENT — This command is designed to be called by other agents, not directly by users.**
> You can invoke it directly for a standalone credential scan, but it is primarily used by `/health-check` and `/infra-orchestrate`.

## How to invoke directly
```
/_sub-credential-scan <path or file>
```

## How it is called by other agents
Other agents invoke this subagent with:
```
Run /_sub-credential-scan on <path> and return findings before proceeding.
```

---

## Your Task

Scan for credentials and secrets in: **$ARGUMENTS**

If `$ARGUMENTS` is empty, scan the entire repository excluding `.git/`.

---

## Scan Process

### Patterns to flag as CRITICAL (plaintext secrets)

Search for these patterns in all `.ps1`, `.py`, `.yml`, `.yaml`, `.sh`, `.json`, `.ini`, `.cfg`, `.txt` files:

```
# Password patterns
-Password\s+["'][^"'${}()\s]{4,}["']
password\s*[=:]\s*["'][^"'${}()\s]{4,}["']
passwd\s*[=:]\s*["'][^"'${}()\s]{4,}["']
pwd\s*[=:]\s*["'][^"'${}()\s]{4,}["']

# API keys and tokens
api[_-]?key\s*[=:]\s*["'][A-Za-z0-9+/\-_]{16,}["']
token\s*[=:]\s*["'][A-Za-z0-9+/\-_]{20,}["']
secret\s*[=:]\s*["'][A-Za-z0-9+/\-_]{16,}["']

# Base64-encoded basic auth
Basic\s+[A-Za-z0-9+/]{20,}={0,2}

# Private key material
BEGIN\s+(RSA|EC|OPENSSH|PGP)\s+PRIVATE KEY

# Connection strings with embedded credentials
Server=.*;Password=[^;]{4,}
mongodb://[^:]+:[^@]{4,}@
```

### Safe patterns (DO NOT flag these)

These are credential-safe patterns already using best practices:
- `$creds` or `$credential` (PowerShell credential object)
- `Get-Credential`
- `$env:VARIABLE_NAME`
- `"{{ vault_`  (Ansible Vault)
- `Read-Host -AsSecureString`
- `[Parameter(Mandatory)]` with `[SecureString]`
- `$env:` prefix on any variable
- Comments explaining what a variable should contain

### Output format

```
## Credential Scan Results
Scanned: <path>
Files checked: <count>
Issues found: <count>

### 🔴 CRITICAL — Plaintext Credentials Found

File: <relative path>
Line: <line number>
Pattern: <which pattern matched>
Recommendation: Replace with Get-Credential / $env: / Ansible Vault

[repeat for each finding — NEVER show the actual credential value]

### ✅ No issues found in:
<list of files that passed>

### Summary
CRITICAL: <count>
Files affected: <count>
Recommended action: <immediate / review / none>
```

**Critical rule: Never display the actual secret value in the output.** Only show the file path, line number, and pattern type.

---

## Return value (when called as subagent)

Return a structured summary that the calling agent can act on:
```
CREDENTIAL_SCAN_RESULT:
status: PASS | FAIL | WARNING
critical_count: <number>
files_affected: [list of paths]
blocking: true | false
```

If `blocking: true`, the calling agent should halt and require the user to remediate before proceeding.
