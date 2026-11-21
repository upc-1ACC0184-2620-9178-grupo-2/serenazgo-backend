# Backend — Asignación de serenazgo (Ventanilla)

API REST en **Python (FastAPI)** con **Domain-Driven Design**: un *bounded context* por área
del negocio, cada uno con sus capas. El frontend Angular es un proyecto aparte y se conecta
por HTTP/JSON (el contrato de la API no depende de la estructura interna).

## Ejecutar

Ejecuta los comandos **uno por uno** dentro de la carpeta que contiene `app/` y `requirements.txt`.

**Windows (PowerShell)**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Si PowerShell bloquea la activación: `Set-ExecutionPolicy -Scope Process Bypass` y vuelve a activar.
Si `uvicorn` no se reconoce: `python -m uvicorn app.main:app --reload --port 8000`.

**Linux / macOS**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- API: http://127.0.0.1:8000 · documentación interactiva: http://127.0.0.1:8000/docs
- CORS: por defecto permite http://localhost:4200 (Angular). Otros orígenes:
  `ORIGENES_PERMITIDOS="https://mi-sitio.com,http://localhost:4200"`.
- Pruebas: `python -m pytest -q` (31 pruebas: algoritmos vs NetworkX, dominio, planificación, contrato HTTP y reglas de arquitectura).

## Bounded contexts

| Contexto | Responsabilidad | Agregados / servicios de dominio |
|---|---|---|
| `network` Red vial | Grafo G1, caminos mínimos, bloqueos | `GraphProvider` (puerto), Dijkstra, `CaminosMinimos` |
| `incidents` Incidentes | Registro y ciclo de vida de incidentes | `Incidente` (activo → atendido) |
| `fleet` Flota | Unidades y bases, disponibilidad | `Unidad`, `Base` |
| `dispatch` Despacho (núcleo) | Recomendar, confirmar y escalar asignaciones | `Despachador`, Ford-Fulkerson, `Propuesta`, `PoliticaDePrioridad` |
| `scheduling` Planificación de turno | El día de 8 h de todos los serenazgos: rutas multi-evento, reloj, cancelaciones, redistribución | `PlanDeTurno`, `Planificador`, `Redistribuidor`, algoritmo húngaro |
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

## Planificación de turno (`scheduling`)

El despacho clásico (`dispatch`) empareja 1 unidad con 1 incidente. Este contexto planifica **todo el turno**:
cada serenazgo recibe una *ruta* de varios eventos (p. ej. eventos 1 y 2 → serenazgo 1; 3 y 4 → serenazgo 2),
con fechas y horas, y el plan **cambia con cada evento** (llegada, cancelación, baja de una unidad).

- **Turno:** dura al menos 8 horas (regla de dominio; `horas < 8` → 422). Soporta 100 o más serenazgos.
- **Reloj:** `POST /api/plan/reloj` avanza el tiempo; las tareas que ya salieron quedan *comprometidas* y el resto se replanifica.
- **Agenda:** parte de los eventos se conoce de antemano (programados, con fecha y hora); la unidad sale justo a tiempo.
- **Cancelados:** `POST /api/plan/eventos/{id}/cancelar` libera al serenazgo y **reasigna** (lo sin cobertura puede entrar ahora).
- **Redistribuir:** `POST /api/plan/redistribuir` mueve los serenazgos libres hacia donde hay demanda
  (k-medianas voraz + algoritmo húngaro para minimizar el traslado total).
- **¿Qué pasa si…?:** `POST /api/plan/que-pasa-si` simula una cancelación o la baja de una unidad sobre una copia del plan.
- **Estrategias** (`/api/plan/estrategias/comparar`): *rápida* (menor respuesta), *equilibrada* (reparte la carga),
  *concentrada* (agrupa eventos cercanos en pocas unidades y deja las demás libres).

Algoritmo: inserción más barata por prioridad + búsqueda local (reubicar eventos), sobre la función de costo
`retraso·peso + respuesta + viaje + balance·carga² + costo_activación`, con Dijkstra para los tiempos de viaje.

| Método y ruta | Descripción |
|---|---|
| GET /api/plan | Estado completo: turno, serenazgos con sus tareas, eventos, métricas |
| POST /api/plan/escenario | Genera un día (`n_serenazgos`, `n_eventos`, `horas`≥8, `pct_programados`, `estrategia`) |
| POST /api/plan/reloj | `{"minutos": 60}` avanza el reloj |
| POST /api/plan/eventos | Registra un evento nuevo ahora y lo asigna |
| POST /api/plan/eventos/{id}/cancelar | Cancela y reasigna |
| POST /api/plan/serenazgos/{id}/baja | Saca una unidad de servicio y reasigna |
| GET /api/plan/serenazgos/{id}/ruta | Recorrido por calles de sus eventos |
| POST /api/plan/optimizar · /estrategia · /redistribuir · /que-pasa-si | Ver arriba |

## Despliegue en Railway
1. Sube esta carpeta (con `Procfile`). Railway instala `requirements.txt` y ejecuta el `Procfile`:
   `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}` (la app **debe** escuchar en `0.0.0.0` y en el `PORT` que da Railway).
2. En *Settings → Networking* genera el dominio público; el puerto del dominio debe ser el mismo que usa la app (8080).
   La URL pública es `https://<tu-app>.up.railway.app` **sin** `:8080`.
3. CORS: el dominio de Vercel `https://serenazgo-frontend1.vercel.app` ya está permitido. Para otro dominio, en *Variables*:
   `ORIGENES_PERMITIDOS=https://otro.vercel.app,http://localhost:4200`
   (y opcional `ORIGEN_REGEX=https://.*\.vercel\.app` para las vistas previas de Vercel).
4. Comprueba: abrir `https://<tu-app>.up.railway.app/docs` y `/api/plan`.
5. Nota: el estado vive en memoria; si Railway reinicia el servicio, se genera un escenario nuevo.

## Agregar un contexto nuevo
1. Crear `app/<nombre>/{domain,application,infrastructure,interfaces}`.
2. Si necesita datos de otro contexto, declarar un puerto en su `domain/` y un adaptador en `infrastructure/`.
3. Si debe reaccionar a algo, suscribirse al evento desde `infrastructure/suscriptores.py`.
4. Registrarlo en `container.py` y `main.py`.

## Opciones
- `DATASET_CSV=ruta.csv`: dataset real de la MPC (columnas N_DE_CASO, TIPOLOGIA, DIRECCION).
- `RED=osmnx`: red real con OSMnx (`pip install osmnx`; sin probar).
