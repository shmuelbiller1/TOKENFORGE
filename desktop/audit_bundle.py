"""Audit a frozen desktop build before packaging it for release.

Only runtime components should go to users. Source tests, server configuration,
Docker files and deployment samples remain in GitHub, not in the downloaded app.
"""
import argparse
import sys
from pathlib import Path


def audit(path: Path) -> None:
    if not path.is_dir():
        raise AssertionError(f"Frozen desktop bundle is missing: {path}")

    if sys.platform == "darwin":
        executable = path / "Contents" / "MacOS" / "TokenForge"
        support_roots = [path / "Contents" / "Frameworks", path / "Contents" / "Resources"]
    else:
        executable = path / ("TokenForge.exe" if sys.platform == "win32" else "TokenForge")
        support_roots = [path / "_internal"]
        visible = {entry.name for entry in path.iterdir()}
        expected = {executable.name, "_internal"}
        if visible != expected:
            raise AssertionError(f"Unexpected launcher-folder items: {sorted(visible - expected)}; missing: {sorted(expected - visible)}")

    if not executable.is_file():
        raise AssertionError(f"Launcher missing: {executable}")
    if not any(root.is_dir() for root in support_roots):
        raise AssertionError("Bundled runtime libraries are missing")

    data = list(path.rglob("tiktoken_cache"))
    if not any(item.is_dir() for item in data):
        raise AssertionError("Offline tokenizer cache is missing from the bundle")

    unwanted = {
        "test_engine.py", "test_engine_api.py", "test_iteration3.py",
        "test_release_safety.py", "backend_test.py", "server.py",
        ".env.example", ".dockerignore", "Dockerfile",
        "requirements-core.txt", "requirements-desktop.txt",
        "requirements.txt",
    }
    found = [str(p.relative_to(path)) for p in path.rglob("*") if p.is_file() and p.name in unwanted]
    if found:
        raise AssertionError("Development or server files in user-facing bundle: " + ", ".join(found[:20]))

    backend_copies = [str(p.relative_to(path)) for p in path.rglob("backend") if p.is_dir()]
    if backend_copies:
        raise AssertionError("Bundled backend source tree is not needed: " + ", ".join(backend_copies))

    print(f"Desktop runtime bundle clean: {path} (no developer tests or backend source copied)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path, help="PyInstaller output directory or macOS .app")
    args = parser.parse_args()
    audit(args.package)


if __name__ == "__main__":
    main()
