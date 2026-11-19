from __future__ import annotations

from app.incidents.domain.incidente import Incidente
from app.incidents.domain.repositorio import IncidenteRepository


class IncidentesEnMemoria(IncidenteRepository):
    def __init__(self) -> None:
        self._d: dict[str, Incidente] = {}

    def todos(self): return list(self._d.values())
    def por_id(self, id_caso): return self._d.get(id_caso)
    def guardar(self, incidente): self._d[incidente.id_caso] = incidente
