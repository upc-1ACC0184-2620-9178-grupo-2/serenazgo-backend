"""Contrato HTTP que consume el frontend Angular + comunicación entre contextos por eventos."""
import pytest
from fastapi.testclient import TestClient

from app.container import Contenedor
from app.main import crear_app


@pytest.fixture()
def cliente():
    return TestClient(crear_app(Contenedor()))


def test_contrato_red_estado_asignacion(cliente):
    red = cliente.get("/api/red").json()
    assert set(red) == {"limites", "nodos", "aristas", "bloqueados", "bases", "n_nodos", "n_aristas", "anclaje", "distrito"}
    assert red["n_nodos"] == 1503 and len(red["bases"]) == 3

    est = cliente.get("/api/estado").json()
    assert set(est) == {"ciclo", "hora", "tmax", "umbrales", "tipologias", "incidentes", "unidades", "bases"}
    assert len(est["incidentes"]) == 50 and len(est["unidades"]) == 94
    assert set(est["incidentes"][0]) == {"id_caso", "tipologia", "direccion", "prioridad", "x", "y",
                                          "nodo_vial", "estado", "orden"}
    assert set(est["unidades"][0]) == {"id", "tipo", "id_base", "disponible", "incidente_asignado", "etiqueta"}

    a = cliente.get("/api/asignacion").json()
    assert set(a) == {"asignaciones", "sin_cobertura", "por_base", "metricas"}
    assert set(a["asignaciones"][0]) == {"incidente_id", "unidad_id", "unidad", "base_id", "base",
                                         "tiempo", "ruta", "alternativas"}
    assert set(a["metricas"]) == {"incidentes_activos", "atendibles", "unidades_disponibles", "unidades_total",
                                  "tiempo_medio", "flujo_maximo", "tmax", "calculo_ms"}
    assert a["metricas"]["atendibles"] == len(a["asignaciones"]) > 0


def test_confirmar_actualiza_incidentes_flota_y_auditoria_por_eventos(cliente):
    a = cliente.get("/api/asignacion").json()["asignaciones"][0]
    r = cliente.post("/api/asignacion/confirmar", json={"pares": [
        {"incidente_id": a["incidente_id"], "unidad_id": a["unidad_id"], "tiempo": a["tiempo"]}]})
    assert r.status_code == 200 and r.json() == {"confirmadas": 1}

    est = cliente.get("/api/estado").json()
    assert all(i["id_caso"] != a["incidente_id"] for i in est["incidentes"])      # Incidentes reaccionó
    u = next(u for u in est["unidades"] if u["id"] == a["unidad_id"])
    assert not u["disponible"] and u["incidente_asignado"] == a["incidente_id"]   # Flota reaccionó
    log = cliente.get("/api/decisiones").json()
    assert any(d["tipo"] == "confirmacion" and d["incidente_id"] == a["incidente_id"] for d in log)  # Auditoría

    # misma unidad otra vez -> 409 con `detail` (el frontend lo muestra)
    r = cliente.post("/api/asignacion/confirmar", json={"pares": [
        {"incidente_id": a["incidente_id"], "unidad_id": a["unidad_id"]}]})
    assert r.status_code == 409 and "detail" in r.json()


def test_confirmar_es_todo_o_nada(cliente):
    asig = cliente.get("/api/asignacion").json()["asignaciones"]
    bueno, malo = asig[0], asig[1]
    r = cliente.post("/api/asignacion/confirmar", json={"pares": [
        {"incidente_id": bueno["incidente_id"], "unidad_id": bueno["unidad_id"]},
        {"incidente_id": malo["incidente_id"], "unidad_id": 99999}]})
    assert r.status_code == 409
    est = cliente.get("/api/estado").json()
    assert any(i["id_caso"] == bueno["incidente_id"] for i in est["incidentes"])  # no se confirmó nada


def test_registrar_incidente_y_validacion(cliente):
    x, y = cliente.get("/api/red").json()["nodos"][0]            # un punto dentro de Ventanilla
    ok = cliente.post("/api/incidentes", json={"tipologia": "Robo en vía pública", "direccion": "Calle 1",
                                               "prioridad": "A", "x": x, "y": y})
    assert ok.status_code == 201 and ok.json()["id_caso"] == "N001"
    assert len(cliente.get("/api/estado").json()["incidentes"]) == 51
    fuera = cliente.post("/api/incidentes", json={"tipologia": "Robo", "direccion": "Calle 1",
                                                  "prioridad": "A", "x": 99, "y": 2})
    assert fuera.status_code == 422 and "detail" in fuera.json()


def test_unidad_y_bloqueo_de_red(cliente):
    r = cliente.patch("/api/unidades/1", json={"disponible": False})
    assert r.status_code == 200 and r.json()["disponible"] is False
    assert cliente.patch("/api/unidades/9999", json={"disponible": True}).status_code == 404

    red = cliente.get("/api/red").json()
    a, b = red["aristas"][0]
    assert cliente.post("/api/red/bloqueo", json={"desde": a, "hasta": b}).status_code == 200
    assert cliente.get("/api/red").json()["bloqueados"] == [[min(a, b), max(a, b)]] or \
        len(cliente.get("/api/red").json()["bloqueados"]) == 1
    assert cliente.post("/api/red/bloqueo", json={"desde": a, "hasta": b}).status_code == 404
    assert cliente.delete("/api/red/bloqueo").json() == {"bloqueados": 0}


def test_nuevo_ciclo_y_escalamiento(cliente):
    assert cliente.post("/api/ciclo/nuevo").json() == {"ciclo": 2}
    assert cliente.post("/api/escalar", json={"incidentes": ["0001", "0002"]}).json() == {"escalados": 2}
    tipos = {d["tipo"] for d in cliente.get("/api/decisiones").json()}
    assert {"ciclo", "escalamiento", "recomendacion"} <= tipos or {"ciclo", "escalamiento"} <= tipos


def test_cors_para_angular(cliente):
    r = cliente.options("/api/red", headers={"Origin": "http://localhost:4200",
                                             "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:4200"


def test_cors_permite_el_frontend_desplegado_en_vercel(cliente):
    r = cliente.options("/api/plan", headers={"Origin": "https://serenazgo-frontend1.vercel.app",
                                              "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "https://serenazgo-frontend1.vercel.app"
    ajeno = cliente.options("/api/plan", headers={"Origin": "https://sitio-ajeno.com",
                                                  "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in ajeno.headers
