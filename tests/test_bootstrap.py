"""Tests for the pure parts of fernweh.py's self-installing bootstrap.

Full end-to-end bootstrapping (creating a real .venv, installing over the
network, re-exec'ing into it) isn't exercised here — see TESTING.md for the
manual fresh-clone verification steps for that. What's covered here is the
logic that decides *whether* those steps are needed, loaded directly from the
script by path (not via `import fernweh`) so it can't collide with the
`fernweh` package under `src/`.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "fernweh.py"
_spec = importlib.util.spec_from_file_location("fernweh_entrypoint", _SCRIPT_PATH)
bootstrap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bootstrap)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Point the bootstrap module's paths at a throwaway directory."""
    requirements_file = tmp_path / "requirements.txt"
    requirements_file.write_text("pygame-ce>=2.5,<3\n")
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()

    monkeypatch.setattr(bootstrap, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(bootstrap, "REQUIREMENTS_FILE", requirements_file)
    monkeypatch.setattr(bootstrap, "VENV_DIR", venv_dir)
    monkeypatch.setattr(bootstrap, "INSTALL_MARKER", venv_dir / ".requirements.sha256")
    return tmp_path


def test_requirements_hash_is_deterministic(sandbox) -> None:
    assert bootstrap._requirements_hash() == bootstrap._requirements_hash()


def test_requirements_hash_changes_with_content(sandbox) -> None:
    original = bootstrap._requirements_hash()
    bootstrap.REQUIREMENTS_FILE.write_text("pygame-ce>=2.5,<3\nsomething-else\n")
    assert bootstrap._requirements_hash() != original


def test_dependencies_not_up_to_date_without_marker(sandbox) -> None:
    assert bootstrap._dependencies_up_to_date() is False


def test_dependencies_up_to_date_when_marker_matches(sandbox) -> None:
    bootstrap.INSTALL_MARKER.write_text(bootstrap._requirements_hash())
    assert bootstrap._dependencies_up_to_date() is True


def test_dependencies_stale_when_requirements_change_after_install(sandbox) -> None:
    bootstrap.INSTALL_MARKER.write_text(bootstrap._requirements_hash())
    bootstrap.REQUIREMENTS_FILE.write_text("pygame-ce>=2.5,<3\nnew-dep\n")
    assert bootstrap._dependencies_up_to_date() is False


def test_venv_python_path_is_platform_dependent(sandbox, monkeypatch) -> None:
    monkeypatch.setattr(bootstrap.sys, "platform", "win32")
    assert bootstrap._venv_python() == sandbox / ".venv" / "Scripts" / "python.exe"

    monkeypatch.setattr(bootstrap.sys, "platform", "linux")
    assert bootstrap._venv_python() == sandbox / ".venv" / "bin" / "python"


def test_running_inside_venv_uses_sys_prefix_not_executable_path(sandbox, monkeypatch) -> None:
    # Regression test: `.venv/bin/python` is frequently a symlink to the base
    # interpreter, so comparing `sys.executable` against it after resolving
    # symlinks would wrongly report "already inside the venv" even when the
    # venv was never activated. `sys.prefix` is the correct signal.
    monkeypatch.setattr(bootstrap.sys, "prefix", str(sandbox / ".venv"))
    assert bootstrap._running_inside_venv() is True

    monkeypatch.setattr(bootstrap.sys, "prefix", sys.base_prefix)
    assert bootstrap._running_inside_venv() is False
