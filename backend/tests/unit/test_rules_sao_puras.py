"""As regras puras não podem importar Django (testáveis sem banco, fáceis de explicar)."""

import ast
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parents[2] / "auctions" / "rules"


def test_rules_nao_importam_django():
    for path in RULES_DIR.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                assert not name.startswith(("django", "rest_framework", "channels")), (
                    f"{path.name} importa {name}"
                )
