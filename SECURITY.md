# Security Policy

## Reporting a Security Issue

If you discover a security issue in this repository — such as hardcoded credentials, exposed API keys, or an insecure scripting pattern — please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, report it via:

- **Email:** Contact the repo owner via GitHub (humbledgeeks-allen) with the subject line `[SECURITY] cisco-ucs-python`

- **GitHub Private Advisory:** Use GitHub's built-in security advisory feature if available on this repository

Include in your report:

- The file path and line number where the issue was found

- A description of the vulnerability and its potential impact

- Suggested remediation (if you have one)

---

## Credential and Secret Policy

This repository enforces a **zero hardcoded credentials** policy. The following are **never** acceptable in any committed file:

- Plaintext passwords in scripts or playbooks

- API keys, tokens, or bearer credentials

- SSH private keys

- SNMP community strings

- Database connection strings with embedded passwords

- Any value matching patterns like `password = "..."`, `api_key = "..."`, `token = "..."`

### Acceptable Credential Patterns

**PowerShell:**

```powershell

# Runtime prompt

$credential = Get-Credential

# Encrypted credential file (machine/user-specific — safe to reference in scripts)

$credential = Import-Clixml -Path "$env:USERPROFILE\.creds\vcenter-creds.xml"

# Environment variable (CI/CD)

$password = $env:VCENTER_PASSWORD

```text

**Ansible:**

```yaml

# Ansible Vault variables — vault_ prefix convention

password: "{{ vault_vcenter_password }}"
no_log: true

```

---

## CI/CD Security Scanning

The CI/CD pipeline (`.github/workflows/lint.yml`) automatically scans all pull requests for:

- Hardcoded password patterns (`password=`, `passwd=`, `Password =`)

- API key patterns (`api_key=`, `apikey=`, `x-api-key:`)

- Token patterns (`token=`, `bearer`)

- Base64-encoded credentials in scripts

- SSH private key headers (`-----BEGIN RSA PRIVATE KEY-----`)

**Pull requests that fail the credential scan will not be merged.**

---

## Handling a Discovered Credential

If a credential is accidentally committed:

1. **Rotate the credential immediately** — assume it is compromised

2. Notify the relevant system owner

3. Remove the credential from the file and replace with a safe pattern

4. Use `git filter-branch` or BFG Repo Cleaner to remove it from git history

5. Force-push the cleaned history to the remote

> Removing a credential from a file is **not sufficient** — it remains in git history until history is rewritten.

---

## Responsible Disclosure Timeline

| Step | Target |
| --- | --- |
| Acknowledge receipt of report | 48 hours |
| Confirm and assess the issue | 5 business days |
| Remediate and close | 14 business days |
| Credit reporter (if desired) | In CHANGELOG at next release |

---

## Supported Versions

Security fixes are applied to the `main` branch only. There are no long-term support branches in this repository.
