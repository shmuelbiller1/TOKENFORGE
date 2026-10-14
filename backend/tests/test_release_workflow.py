"""Regression guards for publicly downloadable desktop releases."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/desktop-release.yml"
ISS = ROOT / "packaging/windows/TokenForge.iss"


def test_release_publication_requires_complete_artifacts():
    text = WORKFLOW.read_text(encoding="utf-8")
    for name in (
        "TokenForge-Windows-x64.zip",
        "TokenForge-Setup-Windows-x64.exe",
        "TokenForge-Portable-Windows-x64.exe",
        "TokenForge-Linux-x64.tar.gz",
        "TokenForge-macOS-*.zip",
        "SHA256SUMS.txt",
    ):
        assert name in text
    assert "Refuse incomplete desktop releases" in text
    assert "test -s" in text
    assert "fail_on_unmatched_files: true" in text
    assert "Verify each public release download" in text
    assert "gh release view" in text
    assert "needs.build.result == 'success'" in text


def test_no_uncontrolled_main_branch_releases():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "startsWith(github.ref, 'refs/tags/v')" in text
    assert "startsWith(github.event.head_commit.message, 'publish: TokenForge v0.3.8')" in text
    assert "tag_name: ${{ startsWith(github.ref, 'refs/tags/v') && github.ref_name || 'v0.3.8' }}" in text
    assert "contents: write" in text
    assert "github.ref == 'refs/heads/main'" in text


def test_installer_version_matches_release():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    iss = ISS.read_text(encoding="utf-8")
    assert '#define AppVersion "0.3.8"' in iss
    assert "#ifndef AppVersion" in iss
    assert '"/DAppVersion=$version"' in workflow
    assert "github.ref_name" in workflow
