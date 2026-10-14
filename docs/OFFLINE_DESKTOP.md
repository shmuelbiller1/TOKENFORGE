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

**For a normal Windows download**, use the latest complete public release:
https://github.com/shmuelbiller1/TOKENFORGE/releases/latest

Choose `TokenForge-Setup-Windows-x64.exe` for desktop/Start Menu installation,
`TokenForge-Portable-Windows-x64.exe` for one standalone file, or
`TokenForge-Windows-x64.zip` for a portable folder.

Only a release that lists these actual executable assets is a working app
download. GitHub's automatic "Source code (zip)" and "Source code (tar.gz)"
files are **not** Windows applications. GitHub Actions artifacts, by contrast,
are developer build bundles and may require a GitHub sign-in and a second ZIP
extraction. Normal users should use **Releases**, not **Actions**.

New version tags still build and publish all supported desktop formats. The
release workflow checks that all platform packages exist, checks the Windows
ZIP, publishes SHA-256 checksums, and verifies the public release assets.
The corrected release is v0.3.8; the earlier v0.3.5 publication was empty.

### What should be inside the portable ZIP?

The Windows portable ZIP is deliberately organized as one application folder:

```text
TokenForge/
  TokenForge.exe        ← double-click to start
  _internal/            ← required Python runtime and offline tokenizer data
```

Do **not** move `TokenForge.exe` away from its `_internal` folder, and do not
delete the support directory. It contains bundled runtime libraries rather
than sample documents to be processed.

The download **does not need** the source repository's automated tests,
example environment settings, backend web server, Docker instructions, or
deployment files. The release build now excludes those files, and the
packaging workflow checks for accidental additions before publishing.

If you prefer a single item with no visible support folder, choose
`TokenForge-Portable-Windows-x64.exe` instead. It is easier to copy to USB,
although its first launch may be slower because it extracts its internal
runtime temporarily.

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

The corrected v0.3.8 release provides **three Windows choices**:

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

The installer, portable folder, and single EXE use the same desktop program, including the R&D History window in v0.3.8 and newer. The packages are not yet code-signed or notarized.
