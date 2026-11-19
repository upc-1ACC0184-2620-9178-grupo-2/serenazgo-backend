"""Auditoría: registra todo evento de dominio sin conocer a los demás contextos (RNF04)."""
from __future__ import annotations

from dataclasses import fields
from enum import Enum

from app.audit.domain.registro import AuditoriaRepository, RegistroDeDecision
from app.shared.kernel.eventos import EventoDeDominio


def _plano(v):
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, tuple):
        return list(v)
    return v


class ServicioAuditoria:
    def __init__(self, repo: AuditoriaRepository):
        self._repo = repo

    def al_evento(self, e: EventoDeDominio) -> None:
        datos = {f.name: _plano(getattr(e, f.name)) for f in fields(e) if f.name != "ocurrido_en"}
        self._repo.agregar(RegistroDeDecision(e.ocurrido_en.isoformat(timespec="seconds"), e.tipo, datos))

    def listar(self, limite: int = 200) -> list[dict]:
        return [r.a_dict() for r in reversed(self._repo.recientes(limite))]
