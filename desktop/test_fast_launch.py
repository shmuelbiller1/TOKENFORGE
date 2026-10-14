"""Fast desktop startup and native file-open contract tests."""
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "desktop" / "app.py"

def test_module_import_does_not_load_optimizer():
    output = subprocess.check_output([sys.executable, "-c",
        "import sys; import desktop.app; print('optimizer' in sys.modules)"],
        cwd=ROOT, text=True)
    assert output.strip() == "False"

def test_open_with_and_finder_hooks_are_present():
    code = APP.read_text(encoding="utf-8")
    ast.parse(code)
    assert "::tk::mac::OpenDocument" in code
    assert "open_paths(initial,auto_start=True)" in code

def test_ci_matrix_expressions_are_not_escaped():
    workflow = (ROOT / ".github/workflows/desktop-release.yml").read_text(encoding="utf-8")
    assert "runs-on: ${{ matrix.os }}" in workflow
    assert chr(92) + "${{" not in workflow

def test_os_open_files_are_added_once_and_automatically_started(tmp_path):
    from desktop.app import Desktop
    p=tmp_path/"file with spaces.txt"
    p.write_text("hello there",encoding="utf-8")
    class FileList:
        def __init__(self): self.items=[]
        def insert(self,_at,value): self.items.append(value)
    class RunButton:
        def cget(self,_key): return "normal"
    class Status:
        def set(self,_text): pass
    class FakeDesktop:
        def __init__(self):
            self.files=[]
            self.list=FileList()
            self.run=RunButton()
            self.status=Status()
            self.started=0
        def start(self): self.started+=1
    d=FakeDesktop()
    assert Desktop.open_paths(d,[str(p)],auto_start=True)==1
    assert Desktop.open_paths(d,[str(p)],auto_start=True)==0
    assert d.files==[str(p.resolve())]
    assert d.started==1

def test_both_windows_portable_formats_are_built_and_released():
    builder = (ROOT / "desktop/build.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/desktop-release.yml").read_text(encoding="utf-8")
    assert "--onefile" in builder
    assert "sys.platform != \"win32\"" in builder
    assert "TokenForge-Portable" in builder
    assert "python desktop/build.py --portable" in workflow
    assert "desktop/dist/TokenForge-Portable.exe" in workflow
    assert "TokenForge-Portable-Windows-x64.exe" in workflow
    assert "TokenForge-Windows-x64.zip" in workflow
    assert "TokenForge-Setup-Windows-x64.exe" in workflow
    assert "Single-file offline self-test failed" in workflow
    assert "Start-Process -FilePath $portable" in workflow
    assert "-Wait -PassThru" in workflow


def test_backend_source_not_copied_into_user_download():
    builder = (ROOT / "desktop/build.py").read_text(encoding="utf-8")
    assert '"--add-data",str(root/"backend")' not in builder
    assert "--contents-directory" in builder
    assert "tiktoken_cache" in builder


def test_release_audit_rejects_source_and_test_files(tmp_path):
    import pytest
    from desktop.audit_bundle import audit

    folder = tmp_path / "TokenForge"
    internal = folder / "_internal"
    (internal / "tiktoken_cache").mkdir(parents=True)
    (folder / "TokenForge").write_bytes(b"dummy compiled launcher")
    audit(folder)

    tests = internal / "backend" / "tests"
    tests.mkdir(parents=True)
    (tests / "test_engine.py").write_text("# dev-only test", encoding="utf-8")
    with pytest.raises(AssertionError, match="Development or server files"):
        audit(folder)


def test_release_workflow_runs_the_package_audit():
    workflow = (ROOT / ".github/workflows/desktop-release.yml").read_text(encoding="utf-8")
    assert "python desktop/audit_bundle.py desktop/dist/TokenForge.app" in workflow
    assert "python desktop/audit_bundle.py desktop/dist/TokenForge" in workflow
