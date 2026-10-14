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
a **new** version tag. Only successful tagged workflows publish GitHub Releases assets.
The source-code tar.gz/zip archives are not desktop applications.
https://github.com/shmuelbiller1/TOKENFORGE/releases

### Installing an offline release

- **Windows:** Extract `TokenForge-Windows-x64.zip` and open `TokenForge.exe` inside the
  extracted `TokenForge` folder. Keep the entire folder together.
- **macOS:** Extract `TokenForge-macOS-arm64.zip` on an Apple Silicon Mac and open
  `TokenForge.app`. This build is not for Intel Macs. The unsigned app may need
  manual approval from your operating system.
- **Linux:** Extract `TokenForge-Linux-x64.tar.gz` using `tar -xzf`, then open
  `TokenForge/TokenForge` in a graphical desktop session.

The build pipeline runs a self-test on the packaged executable before upload.
macOS archives now contain the actual `.app`; Linux archives preserve executable
permissions. These packaging fixes apply only to releases built after this change.
The existing v0.3 assets are not automatically replaced.

**Important:** A recovery bundle reconstructs **parsed fragments**, not original
binary files, images, layout, or formatting. Keep original files as backups.
The text output may omit records when a token budget is specified; the bundle
retains the parsed fragments and map. Archives are unsigned until code signing
and macOS notarization are configured.
