from __future__ import annotations

from app.fleet.domain.repositorios import BaseRepository, UnidadRepository
from app.fleet.domain.unidad import Base, Unidad


class UnidadesEnMemoria(UnidadRepository):
    def __init__(self) -> None:
        self._d: dict[int, Unidad] = {}

    def todas(self): return list(self._d.values())
    def por_id(self, id_unidad): return self._d.get(id_unidad)
    def guardar(self, unidad): self._d[unidad.id] = unidad


class BasesEnMemoria(BaseRepository):
    def __init__(self) -> None:
        self._d: dict[int, Base] = {}

    def todas(self): return list(self._d.values())
    def guardar(self, base): self._d[base.id] = base
