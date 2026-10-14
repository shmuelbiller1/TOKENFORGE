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
