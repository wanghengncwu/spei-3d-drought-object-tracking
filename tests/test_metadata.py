from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


def test_public_package_metadata_is_scientific_and_consistent() -> None:
    from spei3d import SOFTWARE_NAME, __version__

    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    project = metadata["project"]
    assert SOFTWARE_NAME == "spei-3d-drought-object-tracking"
    assert project["name"] == SOFTWARE_NAME
    assert project["version"] == __version__ == "1.0.0"
    assert project["authors"] == [
        {"name": "Heng Wang"},
        {"name": "Fuqiang Wang"},
    ]
    assert metadata["project"]["scripts"]["spei3d"] == "spei3d.cli:main"


def test_repository_documents_use_the_public_name() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    citation = Path("CITATION.cff").read_text(encoding="utf-8")
    assert readme.startswith("# SPEI-Based 3-D Drought Object Tracking")
    assert 'title: "SPEI-Based 3-D Drought Object Tracking"' in citation
    assert "The authors" not in Path("pyproject.toml").read_text(encoding="utf-8")
