# TokenForge Offline Desktop

The desktop edition works without a hosted server, login, database, or network.
Choose local files, optimize, copy or save text, and optionally save a recovery bundle.

## Run from source

Install Python 3.11+ (including Tkinter) and run:

```bash
python -m pip install -r backend/requirements-desktop.txt
python desktop/app.py
```

## Build a standalone desktop package

```bash
python -m pip install -r backend/requirements-desktop.txt "pyinstaller>=6.15,<7"
python desktop/build.py
```

A build fetches dependencies and preloads the tokenizer encoding. The resulting
package includes that data, so it can run offline. Build separately on each OS.

For downloadable archives, run the GitHub Desktop packages workflow or create
a version tag. Only successful tagged workflows publish GitHub Releases assets:
https://github.com/shmuelbiller1/TOKENFORGE/releases

**Important:** A recovery bundle reconstructs **parsed fragments**, not original
binary files, images, layout, or formatting. Keep original files as backups.
The text output may omit records when a token budget is specified; the bundle
retains the parsed fragments and map. Archives are unsigned until code signing
and macOS notarization are configured.
