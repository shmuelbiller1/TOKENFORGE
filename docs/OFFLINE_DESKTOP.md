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

## Fast start and direct file opening (new builds)

The desktop window starts before the heavier Python parser and optimization
libraries are imported. Your first optimization still loads those libraries
and then processes the data in a worker thread.

On Windows, the new `TokenForge-Setup-Windows-x64.exe` installer creates a
Start Menu shortcut and adds **Optimize with TokenForge** to File Explorer's
file context menu (on Windows 11 it may appear under *Show more options*).
Users can also drop a file onto the executable or its shortcut. TokenForge
does **not** change the default app for PDF, text or other file formats.

On macOS, the application bundle registers supported files with Finder.
Use *Open With* or drop a file onto the app's Dock icon.

On Linux, the tarball includes `tokenforge.desktop` and `install-user.sh`.
After extracting, run `sh TokenForge/install-user.sh` to install a per-user
application-menu launcher. The launcher passes selected files into TokenForge.

These features are in the newer release branch, not the already-published
v0.3 source-code archive. The installer is not yet code-signed or notarized.
