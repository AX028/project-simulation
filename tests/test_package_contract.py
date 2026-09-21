from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path

import project_simulation


def _pyproject() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    with (root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def test_public_exports_are_unique() -> None:
    exports = project_simulation.__all__
    assert len(exports) == len(set(exports))


def test_every_public_export_exists() -> None:
    missing = [
        name
        for name in project_simulation.__all__
        if not hasattr(project_simulation, name)
    ]
    assert missing == []


def test_package_version_matches_pyproject() -> None:
    data = _pyproject()
    project = data["project"]
    assert isinstance(project, dict)
    assert project_simulation.__version__ == project["version"]


def test_installed_distribution_version_matches_package() -> None:
    assert (
        importlib.metadata.version("project-simulation")
        == project_simulation.__version__
    )


def test_supported_python_floor_matches_mypy_target() -> None:
    data = _pyproject()
    project = data["project"]
    mypy = data["tool"]["mypy"]
    assert isinstance(project, dict)
    assert isinstance(mypy, dict)
    assert project["requires-python"] == ">=3.11"
    assert mypy["python_version"] == "3.11"
