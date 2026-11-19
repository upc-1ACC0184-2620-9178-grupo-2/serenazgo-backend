# Backend — Asignación de serenazgo (Ventanilla)

API REST en **Python (FastAPI)** con **Domain-Driven Design**: un *bounded context* por área
del negocio, cada uno con sus capas. El frontend Angular es un proyecto aparte y se conecta
por HTTP/JSON (el contrato de la API no depende de la estructura interna).

## Ejecutar
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
- API: http://127.0.0.1:8000 · documentación interactiva: http://127.0.0.1:8000/docs
- CORS: por defecto permite http://localhost:4200 (Angular). Otros orígenes:
  `ORIGENES_PERMITIDOS="https://mi-sitio.com,http://localhost:4200"`.
- Pruebas: `python -m pytest -q` (19 pruebas: algoritmos vs NetworkX, dominio, contrato HTTP y reglas de arquitectura).

## Bounded contexts

| Contexto | Responsabilidad | Agregados / servicios de dominio |
|---|---|---|
| `network` Red vial | Grafo G1, caminos mínimos, bloqueos | `GraphProvider` (puerto), Dijkstra, `CaminosMinimos` |
| `incidents` Incidentes | Registro y ciclo de vida de incidentes | `Incidente` (activo → atendido) |
| `fleet` Flota | Unidades y bases, disponibilidad | `Unidad`, `Base` |
| `dispatch` Despacho (núcleo) | Recomendar, confirmar y escalar asignaciones | `Despachador`, Ford-Fulkerson, `Propuesta`, `PoliticaDePrioridad` |
| `audit` Auditoría | Trazabilidad de decisiones (RNF04) | `RegistroDeDecision` |
| `simulation` Simulación (soporte) | Escenario y ciclos de prueba | `ParametrosDeEscenario` |
| `shared/kernel` | Mínimo compartido | `Prioridad`, errores de dominio, `BusDeEventos` |

Cada contexto tiene las mismas capas:
```
app/<contexto>/
  domain/          entidades, value objects, servicios de dominio, puertos (interfaces), eventos
  application/     casos de uso (servicios de aplicación)
  infrastructure/  repositorios en memoria, adaptadores hacia otros contextos, suscriptores de eventos
  interfaces/      router REST (FastAPI) del contexto
```
`app/container.py` es el *composition root* (conecta todo) y `app/main.py` arma la API.
`app/presentation/vista_despacho.py` es una API Composition (BFF): `GET /api/red` y `GET /api/estado`
combinan varios contextos para la pantalla; solo lee.

## Cómo se comunican los contextos

Nunca importándose entre sí en `domain/` ni `application/` (lo verifica `tests/test_arquitectura.py`):

1. **Puertos y adaptadores (consultas).** Despacho declara lo que necesita (`RedVialPort`,
   `IncidentesPort`, `FlotaPort`) con su propio modelo; `dispatch/infrastructure/adaptadores.py`
   los implementa con los servicios de los otros contextos (anti-corruption layer).
2. **Eventos de dominio (efectos).** Al confirmar, Despacho publica `AsignacionConfirmada`;
   Incidentes marca el caso atendido y Flota ocupa la unidad. Auditoría registra todos los eventos.

| Evento | Publica | Reaccionan |
|---|---|---|
| `AsignacionConfirmada` | dispatch | incidents (atendido), fleet (unidad ocupada), audit |
| `RecomendacionCalculada`, `IncidentesEscalados` | dispatch | audit |
| `IncidenteRegistrado` | incidents | audit |
| `UnidadActualizada` | fleet | audit |
| `TramoBloqueado`, `RedRestablecida` | network | audit |
| `CicloIniciado` | simulation | audit |

## API (el frontend la consume tal cual)

| Método y ruta | Contexto | Requisito |
|---|---|---|
| GET /api/red | BFF (network + fleet) | RF05 |
| GET /api/estado | BFF | Incidentes activos, unidades, bases |
| POST /api/ciclo/nuevo | simulation | Nuevo ciclo |
| POST /api/incidentes | incidents | RF01, CU01 |
| PATCH /api/unidades/{id} | fleet | RF02, CU04 |
| GET /api/asignacion | dispatch | RF03, RF04, RF08, CU02 |
| POST /api/asignacion/confirmar | dispatch | RF06, CU03 |
| POST /api/escalar | dispatch | RF08 |
| POST /api/red/bloqueo, DELETE | network | RF07, CU05 |
| GET /api/decisiones | audit | RNF04 |

Errores: el dominio lanza `NoEncontrado` (404), `Conflicto` (409) o `Invalido` (422) y la API
responde `{"detail": "..."}`.

## Agregar un contexto nuevo
1. Crear `app/<nombre>/{domain,application,infrastructure,interfaces}`.
2. Si necesita datos de otro contexto, declarar un puerto en su `domain/` y un adaptador en `infrastructure/`.
3. Si debe reaccionar a algo, suscribirse al evento desde `infrastructure/suscriptores.py`.
4. Registrarlo en `container.py` y `main.py`.

## Opciones
- `DATASET_CSV=ruta.csv`: dataset real de la MPC (columnas N_DE_CASO, TIPOLOGIA, DIRECCION).
- `RED=osmnx`: red real con OSMnx (`pip install osmnx`; sin probar).
