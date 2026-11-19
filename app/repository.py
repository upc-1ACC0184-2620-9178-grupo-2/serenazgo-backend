"""Repositorio en memoria de incidentes, unidades y decisiones (RNF04)."""
from __future__ import annotations

import random
import threading
from datetime import datetime

from .domain import Base, Incidente, Unidad


class Repositorio:
    def __init__(self, bases: list[Base], unidades: list[Unidad],
                 incidentes: list[Incidente], p_disponible: float = 0.45,
                 n_activos: int = 50, semilla: int = 42):
        self.bases = {b.id: b for b in bases}
        self.unidades = {u.id: u for u in unidades}
        self.incidentes = {i.id_caso: i for i in incidentes}
        self.p_disponible = p_disponible
        self.n_activos = n_activos
        self.semilla = semilla
        self.lock = threading.RLock()
        self.decisiones: list[dict] = []
        self.ciclo = 0
        self.hora = ""
        self._llegada = 0
        self._manuales = 0
        self.nuevo_ciclo()

    # --- consultas ---------------------------------------------------------
    def activos(self) -> list[Incidente]:
        return [i for i in self.incidentes.values() if i.estado == "activo"]

    def disponibles(self) -> list[Unidad]:
        return [u for u in self.unidades.values() if u.disponible]

    # --- comandos ----------------------------------------------------------
    def registrar(self, tipo: str, **datos) -> None:
        self.decisiones.append({"ts": datetime.now().isoformat(timespec="seconds"),
                                "tipo": tipo, **datos})
        del self.decisiones[:-1000]

    def nuevo_ciclo(self, semilla: int | None = None) -> None:
        with self.lock:
            self.ciclo += 1
            rng = random.Random(semilla if semilla is not None
                                else self.semilla + self.ciclo - 1)
            for i in self.incidentes.values():
                i.estado = "inactivo"
            pool = list(self.incidentes.values())
            for k, i in enumerate(rng.sample(pool, min(self.n_activos, len(pool)))):
                i.estado, i.orden = "activo", k
            self._llegada = self.n_activos
            for u in self.unidades.values():
                u.disponible = rng.random() < self.p_disponible
                u.incidente_asignado = None
            self.hora = datetime.now().strftime("%H:%M")
            self.registrar("ciclo", ciclo=self.ciclo, activos=len(self.activos()),
                           disponibles=len(self.disponibles()))

    def registrar_incidente(self, tipologia, direccion, prioridad, x, y, nodo) -> Incidente:
        with self.lock:
            self._manuales += 1
            self._llegada += 1
            inc = Incidente(f"N{self._manuales:03d}", tipologia, direccion, prioridad,
                            x, y, nodo, estado="activo", orden=self._llegada)
            self.incidentes[inc.id_caso] = inc
            self.registrar("incidente", incidente=inc.id_caso, prioridad=prioridad)
            return inc

    def set_unidad(self, id_unidad: int, disponible: bool) -> Unidad:
        with self.lock:
            u = self.unidades[id_unidad]
            u.disponible = disponible
            if disponible:
                u.incidente_asignado = None
            self.registrar("unidad", unidad=u.etiqueta, disponible=disponible)
            return u

    def confirmar(self, pares: list[dict], operador: str = "GJ") -> int:
        """Valida y confirma asignaciones (RF06). Todo o nada."""
        with self.lock:
            vistos_i, vistos_u = set(), set()
            for p in pares:
                inc = self.incidentes.get(p["incidente_id"])
                uni = self.unidades.get(p["unidad_id"])
                if inc is None or inc.estado != "activo":
                    raise ValueError(f"El incidente {p['incidente_id']} no está activo.")
                if uni is None or not uni.disponible:
                    raise ValueError(f"La unidad {p['unidad_id']} no está disponible.")
                if p["incidente_id"] in vistos_i or p["unidad_id"] in vistos_u:
                    raise ValueError("Hay incidentes o unidades repetidos.")
                vistos_i.add(p["incidente_id"])
                vistos_u.add(p["unidad_id"])
            for p in pares:
                inc, uni = self.incidentes[p["incidente_id"]], self.unidades[p["unidad_id"]]
                inc.estado = "atendido"
                uni.disponible, uni.incidente_asignado = False, inc.id_caso
                self.registrar("confirmacion", incidente=inc.id_caso, unidad=uni.etiqueta,
                               tiempo=p.get("tiempo"), modificada=bool(p.get("modificada")),
                               operador=operador)
            return len(pares)
