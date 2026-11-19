"""Eventos de dominio y bus en proceso: la forma en que los contextos se comunican."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, ClassVar


@dataclass(frozen=True, kw_only=True)
class EventoDeDominio:
    tipo: ClassVar[str] = "evento"          # etiqueta para la trazabilidad (RNF04)
    ocurrido_en: datetime = field(default_factory=datetime.now)


Manejador = Callable[[EventoDeDominio], None]


class BusDeEventos:
    """Publicación síncrona en proceso. Primero los suscriptores del tipo, luego los globales."""

    def __init__(self) -> None:
        self._por_tipo: dict[type, list[Manejador]] = defaultdict(list)
        self._todos: list[Manejador] = []

    def suscribir(self, tipo: type, manejador: Manejador) -> None:
        self._por_tipo[tipo].append(manejador)

    def suscribir_todos(self, manejador: Manejador) -> None:
        self._todos.append(manejador)

    def publicar(self, evento: EventoDeDominio) -> None:
        for m in self._por_tipo[type(evento)]:
            m(evento)
        for m in self._todos:
            m(evento)
