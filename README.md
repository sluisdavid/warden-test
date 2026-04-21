# Warden

Warden es un servicio de remediacion autonoma para un IDP interno. Recibe eventos de degradacion via webhook, razona con un LLM sobre la causa probable, aplica restricciones de seguridad, ejecuta acciones cuando es seguro hacerlo y escala al on-call cuando se requiere aprobacion humana.

## Objetivos cubiertos

- Ingesta estricta por `POST /webhook`.
- Razonamiento estructurado con salida `action`, `confidence`, `reasoning` y `safe_to_auto`.
- Aplicacion explicita de politicas de seguridad.
- Historial por workload para enriquecer el contexto del LLM.
- Feedback loop a partir de aprobaciones y rechazos humanos.
- API de gestion para salud, eventos y approvals.
- Mocks del orquestador y del sistema de notificaciones.
- Logs JSON, tests automatizados y ejecucion con `docker compose`.

## Stack

- Python 3.12
- FastAPI
- SQLite
- httpx
- pytest
- Docker / Docker Compose

## Arquitectura

### Flujo principal

1. `POST /webhook` valida el payload.
2. Se persiste el evento recibido.
3. Se recuperan los ultimos `N` eventos del mismo workload (`project_id + environment_id`).
4. Warden invoca el motor de razonamiento:
   - `heuristic` por defecto para correr local sin dependencias externas.
   - proveedor remoto configurable via API compatible con OpenAI/Groq.
5. Se aplican restricciones obligatorias:
   - `critical` nunca se autoejecuta.
   - `confidence < 0.7` nunca se autoejecuta.
   - en entornos productivos, `rollback` y `scale_up` requieren aprobacion humana.
6. Si `safe_to_auto=true`, se ejecuta el handler correspondiente.
7. Si `safe_to_auto=false`, se crea un approval request persistente y se notifica al on-call mock.

### Acciones soportadas

- `rollback`
- `restart`
- `scale_up`
- `notify_human`
- `no_action`

## Estructura

```text
.
|-- README.md
|-- Dockerfile
|-- docker-compose.yml
|-- requirements.txt
|-- src/
|   |-- main.py
|   |-- service.py
|   |-- llm.py
|   |-- policy.py
|   |-- repositories.py
|   |-- database.py
|   |-- schemas.py
|   |-- clients.py
|   |-- config.py
|   `-- logging_config.py
|-- mocks/
|   |-- orchestrator_mock.py
|   `-- notifier_mock.py
`-- tests/
    |-- conftest.py
    |-- test_webhook.py
    `-- test_approvals.py
```

## Como correrlo

### Opcion 1: Docker Compose

```bash
docker compose up --build
```

Si quieres mantener secretos fuera del repositorio, copia `.env.example` a `.env` y define ahi tus overrides locales. `docker compose` lee `.env` automaticamente.

En PowerShell tambien puedes usar el wrapper incluido, que hace la eleccion de forma explicita:

- si no hay proveedor definido, pregunta si quieres usar Groq
- si respondes que si, fija `groq` para esa sesion y pide la API key
- si respondes que no, usa `heuristic`
- si `WARDEN_LLM_PROVIDER=groq` ya estaba definido pero falta la key, solo pide la API key

```powershell
Copy-Item .env.example .env
.\start-warden.ps1
```

Para levantarlo en background:

```powershell
.\start-warden.ps1 -Detached
```

Servicios expuestos:

- Warden: `http://localhost:8000`
- Orchestrator mock: `http://localhost:8001`
- Notifier mock: `http://localhost:8002`

### Opcion 2: Local

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload
```

En Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn src.main:app --reload
```

## Variables de entorno

- `WARDEN_DATABASE_URL`: ruta del SQLite. Default `file:/data/warden.db?mode=rwc`
- `WARDEN_HISTORY_LIMIT`: cantidad de eventos historicos a enviar al LLM. Default `5`
- `WARDEN_LLM_PROVIDER`: `heuristic` o proveedor remoto. Default `heuristic`
- `WARDEN_LLM_API_URL`: endpoint compatible con OpenAI/Groq
- `WARDEN_LLM_API_KEY`: token del proveedor
- `WARDEN_LLM_MODEL`: modelo a utilizar
- `WARDEN_ORCHESTRATOR_BASE_URL`: URL del mock/orquestador
- `WARDEN_NOTIFIER_BASE_URL`: URL del mock/notificador
- `WARDEN_PRODUCTIVE_ENVIRONMENTS`: nombres de entornos productivos, separados por coma. Default `prod,production`

## Integracion con Groq

La forma mas simple de evitar hardcodear la API key es usar `.env`, que no se versiona porque esta en `.gitignore`.

1. Crea tu archivo local:

```powershell
Copy-Item .env.example .env
```

2. Edita `.env` y define:

```env
WARDEN_LLM_PROVIDER=groq
WARDEN_LLM_API_URL=https://api.groq.com/openai/v1/chat/completions
WARDEN_LLM_API_KEY=<tu_api_key>
WARDEN_LLM_MODEL=llama-3.1-8b-instant
```

3. Arranca el stack:

```powershell
docker compose up --build
```

Si prefieres no dejar la key ni siquiera en `.env`, usa el wrapper:

```powershell
.\start-warden.ps1
```

Ese script interrumpe el arranque para preguntarte si quieres usar Groq. Si respondes que si, pide la API key en consola solo para la sesion actual y luego ejecuta `docker compose up --build`. Si respondes que no, arranca en modo `heuristic`.

Importante: la API key se inyecta en runtime al contenedor de `warden`; no se escribe en el `Dockerfile` ni queda embebida en la imagen.

El servicio envia al modelo:

- evento actual
- historial relevante del mismo workload
- acciones validas
- feedback de aprobaciones/rechazos previos

## API

### Health

```http
GET /health
```

### Ingesta

```http
POST /webhook
Content-Type: application/json
```

Ejemplo:

```json
{
  "project_id": "payments-api",
  "environment_id": "prod",
  "severity": "high",
  "signal": "P99 latency spiked to 4s after the 14:30 deploy",
  "context": {
    "last_deploy": "v2.3.1",
    "cpu_usage": "85%",
    "error_rate": "12%"
  },
  "timestamp": "2024-04-03T14:45:00Z"
}
```

### Gestion

- `GET /events`
- `GET /events/{id}`
- `GET /approvals`
- `POST /approvals/{id}/approve`
- `POST /approvals/{id}/reject`

## Tests

Instalacion y ejecucion:

```bash
pip install -r requirements.txt
pytest
```

Cobertura funcional incluida:

- validacion estricta del payload
- restricciones de `safe_to_auto`
- autoejecucion de acciones seguras
- creacion de approval requests
- aprobacion y rechazo de acciones humanas

## Logs

Todas las operaciones relevantes se registran en JSON:

- recepcion de evento
- decision del LLM
- aplicacion de restricciones
- ejecucion de accion
- envio de notificaciones
- errores de validacion

## LLM Reasoning

Warden incluye un motor de razonamiento que analiza eventos de degradación y propone una remediación estructurada antes de ejecutar cualquier acción.

### Objetivo

Dado un evento recibido por `POST /webhook`, el servicio debe producir una decisión con el siguiente contrato:

```json
{
  "action": "rollback|restart|scale_up|notify_human|no_action",
  "confidence": 0.0,
  "reasoning": "string",
  "safe_to_auto": false
}
