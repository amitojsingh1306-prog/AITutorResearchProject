# Cross-platform environment setup

Python virtual environments are not portable between macOS and Windows. A copied `.venv` can unzip successfully but still fail because it contains operating-system-specific scripts and binary packages.

Use these setup scripts instead:

## macOS

```bash
./scripts/setup-mac.sh
```

This creates `.venv-mac` and installs the backend dependencies.

Activate it with:

```bash
source .venv-mac/bin/activate
```

## Windows PowerShell

```powershell
.\scripts\setup-windows.ps1
```

This creates `.venv-windows` and installs the backend dependencies.

Activate it with:

```powershell
.\.venv-windows\Scripts\Activate.ps1
```

## Windows Command Prompt

```bat
scripts\setup-windows.bat
```

Activate it with:

```bat
.venv-windows\Scripts\activate.bat
```

## Notes

- Keep `backend/requirements.txt` as the source of truth for backend packages.
- Do not share or commit `.venv`, `.venv-mac`, or `.venv-windows`.
- If dependencies change, rerun the setup script for your operating system.
