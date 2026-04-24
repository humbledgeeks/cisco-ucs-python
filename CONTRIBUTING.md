# Contributing to cisco-ucs-python

## Requirements

- Python 3.8+
- ucsmsdk: `pip install ucsmsdk`
- flake8: `pip install flake8`

## Script Header

All scripts must include a module docstring:

```python
"""
Script: script_name.py
Author: HumbledGeeks / Allen Johnson
Date  : YYYY-MM-DD
Repo  : cisco-ucs-python

Description:
    Brief description of what this script does.
"""
```

## Credential Standards

- Use `os.environ` for all sensitive values
- Never hardcode credentials
- Pattern: `os.environ["UCSM_PASSWORD"]`

## Linting

```bash
flake8 .
```

## Pull Request Checklist

- [ ] Module docstring present with all fields
- [ ] No hardcoded credentials
- [ ] flake8 passes with no errors
- [ ] README updated if new scripts added
