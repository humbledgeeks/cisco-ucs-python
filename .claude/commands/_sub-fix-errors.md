# [SUBAGENT] Error Fixer

> **⚠️ SUBAGENT — This command is designed to be called by `/script-validate`, not directly by users.**
> You can invoke it directly if you have a specific list of errors to fix, but its primary purpose is to receive structured error output from `/script-validate` and apply targeted fixes in a loop.

## How it is called by `/script-validate`
```
Run /_sub-fix-errors on <path> with these findings: <findings list>
```

## How to invoke directly
```
/_sub-fix-errors <path-to-script>
/_sub-fix-errors <path> --errors "<specific error description>"
```

---

## Your Task

Fix errors in: **$ARGUMENTS**

---

## Fix Process

### Step 1 — Parse the error list

Read the findings passed in from `/script-validate` (or read the file yourself and identify issues if called directly). Categorize each error:

| Category | Fix Strategy |
|----------|-------------|
| **Syntax error** | Repair the specific line — bracket mismatch, missing quote, wrong operator |
| **Hardcoded credential** | Replace with safe pattern — see credential fix rules below |
| **Undefined variable** | Add declaration before first use, or add as script parameter |
| **Deprecated cmdlet** | Replace with current equivalent — see deprecation map below |
| **Missing header** | Generate and insert compliant header block |
| **Missing validation block** | Append appropriate validation commands for the platform |
| **Write-Host usage** | Replace with `Write-Output` (pipeline) or `Write-Verbose` (diagnostic) |
| **Missing `set -euo pipefail`** | Insert after shebang line in bash scripts |
| **Missing `name:` on Ansible task** | Derive a descriptive name from the module and args |
| **Plaintext password in Ansible** | Replace with `{{ vault_<variable_name> }}` |
| **Missing `state:` on Ansible module** | Add `state: present` (or appropriate default) |

---

### Step 2 — Apply fixes using these exact rules

#### Credential fixes (PowerShell)

| Pattern found | Replace with |
|--------------|-------------|
| `$password = "value"` | `$password = Read-Host -AsSecureString "Enter password for $targetSystem"` |
| `$password = 'value'` | Same as above |
| `-Password "value"` | `-Credential (Get-Credential -Message "Enter credentials for $targetSystem")` |
| `$apiKey = "value"` | `$apiKey = $env:API_KEY  # Set environment variable API_KEY before running` |
| `$token = "value"` | `$token = $env:AUTH_TOKEN  # Set environment variable AUTH_TOKEN before running` |

Always add a comment above the replacement explaining what credential is needed.

#### Credential fixes (Ansible)

| Pattern found | Replace with |
|--------------|-------------|
| `password: "value"` | `password: "{{ vault_<context>_password }}"` |
| `username: "value"` | `username: "{{ vault_<context>_username }}"` |
| `api_key: "value"` | `api_key: "{{ vault_<context>_api_key }}"` |

Add a comment: `# Requires Ansible Vault — see 07-Ansible Vault in ONTAP-Learning`

#### Deprecation map (PowerShell / PowerCLI)

| Deprecated | Current replacement |
|-----------|-------------------|
| `Get-VMHostNtpServer` | `Get-VMHostNtp` |
| `Set-VMHostNtpServer` | `Add-VMHostNtp` |
| `Get-NcVol` (DataONTAP) | Still valid — note if REST API preferred |
| `Add-PSSnapin VeeamPSSnapin` | Valid for VBR ≤ 11; note VBR 12 auto-loads |
| `Write-Host` | `Write-Output` for pipeline; `Write-Verbose` for diagnostic output |

#### Missing validation block — platform-specific templates

**PowerShell — VMware:**
```powershell
# === Validation ===
Write-Output "Validating configuration..."
Get-VMHost | Select-Object Name, ConnectionState, PowerState | Format-Table -AutoSize
```

**PowerShell — NetApp ONTAP:**
```powershell
# === Validation ===
Write-Output "Validating configuration..."
Get-NcNode | Select-Object Name, IsNodeHealthy | Format-Table -AutoSize
```

**PowerShell — Veeam:**
```powershell
# === Validation ===
Write-Output "Validating last job results..."
Get-VBRBackupSession | Sort-Object CreationTime -Descending |
    Select-Object -First 5 | Select-Object JobName, Result, CreationTime |
    Format-Table -AutoSize
```

**PowerShell — Cisco UCS:**
```powershell
# === Validation ===
Write-Output "Validating UCS state..."
Get-UcsFabricInterconnect | Select-Object Dn, OperState | Format-Table -AutoSize
```

**Ansible — add as final task:**
```yaml
- name: Validate - gather post-configuration facts
  <collection>.facts_module:
    hostname: "{{ hostname }}"
    username: "{{ vault_username }}"
    password: "{{ vault_password }}"
  register: post_config_facts

- name: Validate - confirm expected state
  assert:
    that:
      - post_config_facts is defined
    fail_msg: "Validation failed - check configuration"
    success_msg: "Validation passed"
```

---

### Step 3 — Apply fixes with surgical precision

**Rules for making changes:**
- Fix **only what is on the error list** — do not refactor unrelated code
- Preserve all whitespace, indentation, and formatting outside the changed lines
- For multi-line fixes, maintain the surrounding context's indentation style
- Add a `# FIXED: <brief reason>` comment on changed lines so the diff is self-documenting
- If a fix requires adding imports or module references at the top of the file, do so cleanly

**Logic change rule:**
- If a fix would alter what the script *does* (not just how it's written), STOP and flag it:
  ```
  ⚠️ LOGIC CHANGE REQUIRED — Line <N>
  Issue   : <what the error is>
  Current : <current code>
  Proposed: <what the fix would be>
  Risk    : This changes script behavior — please review before accepting
  ```
  Do not apply logic changes automatically. Present them and wait for confirmation.

---

### Step 4 — Return the fixed script

Present:
1. **Fix summary** — table of every change made
2. **Fixed script** — complete script in a code block with `# FIXED:` markers visible
3. **Signal back to `/script-validate`** for re-validation

```
FIX_RESULT:
fixes_applied: <count>
fixes_skipped: <count — logic changes requiring review>
requires_retest: true
ready_for_retest: true
```

---

### Step 5 — Anything that cannot be auto-fixed

Some issues genuinely require human judgment. Always flag these rather than guessing:

| Issue type | Why it needs human review |
|-----------|--------------------------|
| Broken logic / wrong algorithm | Only the author knows the intent |
| Missing required parameters | Only the author knows what values are needed |
| Deprecated API with no direct replacement | Requires research into the new approach |
| Environment-specific paths or hostnames | Cannot be safely generalized |
| Scripts that require execution to validate | Cannot be tested statically |

For each of these, produce a clear `⚠️ MANUAL FIX NEEDED` block with the specific question the human needs to answer.

---

## Return value summary

```
SUB_FIX_ERRORS_RESULT:
status      : FIXED | PARTIAL | MANUAL_REQUIRED
auto_fixed  : <count>
manual_items: <count>
ready_for_retest: true | false
changes     : [list of { line, original, fixed, reason }]
manual_review: [list of { line, issue, question }]
```
