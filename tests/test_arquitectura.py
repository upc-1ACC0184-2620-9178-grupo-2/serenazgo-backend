"""Reglas de DDD que el código debe cumplir (se verifican leyendo los imports)."""
import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
CONTEXTOS = {"network", "fleet", "incidents", "dispatch", "audit", "simulation"}


def _imports(archivo: Path) -> set[str]:
    out = set()
    for n in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.add(n.module)
    return out


def _archivos(ctx: str, capas: tuple[str, ...]):
    for capa in capas:
        yield from (APP / ctx / capa).glob("*.py")


def test_domain_y_application_no_dependen_de_otros_contextos():
    """Un contexto solo conoce a los demás por puertos (adaptadores en infrastructure)
    o por eventos. El contexto de simulación es el orquestador y queda exceptuado."""
    fallos = []
    for ctx in CONTEXTOS - {"simulation"}:
        for f in _archivos(ctx, ("domain", "application")):
            for imp in _imports(f):
                partes = imp.split(".")
                if partes[0] == "app" and len(partes) > 1 and partes[1] in CONTEXTOS - {ctx}:
                    fallos.append(f"{f.relative_to(APP)} importa {imp}")
    assert not fallos, "\n".join(fallos)


def test_domain_es_puro_sin_frameworks():
    prohibidos = ("fastapi", "pydantic", "starlette", "uvicorn", "networkx")
    fallos = []
    for ctx in CONTEXTOS:
        for f in _archivos(ctx, ("domain",)):
            for imp in _imports(f):
                if imp.split(".")[0] in prohibidos:
                    fallos.append(f"{f.relative_to(APP)} importa {imp}")
    assert not fallos, "\n".join(fallos)


def test_cada_contexto_tiene_sus_capas():
    for ctx in CONTEXTOS:
        for capa in ("domain", "application", "infrastructure", "interfaces"):
            assert (APP / ctx / capa).is_dir(), f"{ctx}/{capa}"
