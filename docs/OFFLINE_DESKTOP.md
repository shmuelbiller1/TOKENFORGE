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

## Windows: choose the download that fits you

After the next tagged release (existing v0.3.5 assets do not change),
the release page will have **three Windows choices**:

| Download | How to run it | Best use |
| --- | --- | --- |
| `TokenForge-Portable-Windows-x64.exe` | Copy this single EXE to a USB drive; double-click it on a Windows x64 PC. No installation or ZIP extraction. | Share one simple file |
| `TokenForge-Windows-x64.zip` | Extract the complete folder; double-click `TokenForge.exe` inside it. Keep the folder together. | Faster startup |
| `TokenForge-Setup-Windows-x64.exe` | Install once; launch from Start or use the file right-click action. | Regular use |

The single-file edition is built with PyInstaller one-file mode. It unpacks
its supporting libraries into a temporary directory during startup and
removes them after exit. Thus its initial window generally opens more slowly
than the folder edition. Both run offline and bundle Python and their
dependencies.

**Public/locked-down computers:** you can download either file to a USB
drive without running it on the public computer. The recipient's Windows x64
computer must allow local unsigned applications. USB portability does not
bypass administrator restrictions. Unsigned downloads may trigger system
security prompts.

Do not choose GitHub's auto-generated `Source code (zip)` or `Source code
(tar.gz)` files to run TokenForge: those are for software developers.

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

Fast-open and installer features are available in the latest published releases. The new single-file USB edition becomes available after its release workflow succeeds on a newer tag. The packages are not yet signed or notarized.
