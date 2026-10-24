import ast
from pathlib import Path

APP_SOURCES = Path(__file__).resolve().parents[1] / "src" / "nox_app"


def test_app_does_not_import_ml_package():
    """The app depends only on the exported-data contract, never on nox_ml code."""
    imported = set()
    for path in APP_SOURCES.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

    assert "nox_ml" not in imported
