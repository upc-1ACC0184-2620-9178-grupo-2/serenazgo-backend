from __future__ import annotations

from app.audit.domain.registro import AuditoriaRepository, RegistroDeDecision


class AuditoriaEnMemoria(AuditoriaRepository):
    def __init__(self, maximo: int = 1000) -> None:
        self._r: list[RegistroDeDecision] = []
        self._max = maximo

    def agregar(self, registro):
        self._r.append(registro)
        del self._r[:-self._max]

    def recientes(self, limite):
        return self._r[-limite:]
