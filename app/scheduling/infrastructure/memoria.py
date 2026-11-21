from __future__ import annotations

from app.scheduling.domain.puertos import PlanRepository


class PlanEnMemoria(PlanRepository):
    def __init__(self) -> None:
        self._plan = None

    def obtener(self):
        return self._plan

    def guardar(self, plan) -> None:
        self._plan = plan
