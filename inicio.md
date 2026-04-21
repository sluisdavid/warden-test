# Inicio rapido

## Levantar el proyecto

Desde la raiz del repositorio:

```powershell
cd warden-test
docker compose down
.\start-warden.ps1
```

Que hace `start-warden.ps1`:

- si no hay proveedor definido, pregunta si deseas usar Groq
- si eliges Groq, solicita la API key solo para la sesion actual
- si no eliges Groq, arranca en modo `heuristic`
- luego ejecuta `docker compose up --build`

## Verificacion inicial

Comprobar que los servicios estan arriba:

```powershell
docker compose ps
```

Verificar salud de Warden:

```powershell
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/health"
```

Verificar configuracion efectiva dentro del contenedor:

```powershell
docker compose exec warden printenv | Select-String "WARDEN_LLM_PROVIDER|WARDEN_LLM_API_KEY|WARDEN_LLM_MODEL"
```

## Endpoints utiles

- Warden health: [http://localhost:8000/health](http://localhost:8000/health)
- Warden docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Eventos: [http://localhost:8000/events](http://localhost:8000/events)
- Approvals: [http://localhost:8000/approvals](http://localhost:8000/approvals)
- Notifier mock: [http://localhost:8002/notifications](http://localhost:8002/notifications)
- Groq logs: [https://console.groq.com/dashboard/logs?cursor=](https://console.groq.com/dashboard/logs?cursor=)

## Approval y reject

Listar approvals pendientes:

```powershell
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/approvals"
```

Aprobar:

```powershell
$approvalId = "<approval_id>"
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/approvals/$approvalId/approve"
```

Rechazar:

```powershell
$approvalId = "<approval_id>"
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/approvals/$approvalId/reject"
```

Consultar un evento:

```powershell
$eventId = "<event_id>"
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/events/$eventId"
```

## Casos de prueba

### 1. Autoejecucion valida

Espera `restart` y `completed`.

```powershell
$bodyAuto = @{
  project_id     = "checkout-api"
  environment_id = "qa"
  severity       = "medium"
  signal         = "Pod crashloop requires restart"
  context        = @{
    pod = "checkout-api-784d"
  }
  timestamp      = "2024-04-03T14:55:00Z"
} | ConvertTo-Json -Depth 5

$responseAuto = Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8000/webhook" `
  -ContentType "application/json" `
  -Body $bodyAuto

$responseAuto
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/events/$($responseAuto.event_id)"
```

### 2. Approval obligatorio por prod + rollback

Espera `pending_approval`.

```powershell
$bodyRollback = @{
  project_id     = "payments-api"
  environment_id = "prod"
  severity       = "high"
  signal         = "Recent deploy caused elevated latency and rollback is recommended"
  context        = @{
    last_deploy = "v2.3.1"
    cpu_usage   = "85%"
    error_rate  = "12%"
  }
  timestamp      = "2024-04-03T14:45:00Z"
} | ConvertTo-Json -Depth 5

$responseRollback = Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8000/webhook" `
  -ContentType "application/json" `
  -Body $bodyRollback

$responseRollback
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/events/$($responseRollback.event_id)"
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/approvals"
```

### 3. Approval obligatorio por critical

Espera `pending_approval` aunque el LLM sugiera una accion ejecutable.

```powershell
$bodyCritical = @{
  project_id     = "orders-api"
  environment_id = "qa"
  severity       = "critical"
  signal         = "Pods crashlooping after rollout, restart may help"
  context        = @{
    last_deploy  = "v4.8.0"
    pod_count    = 6
    failing_pods = 4
  }
  timestamp      = "2024-04-03T15:05:00Z"
} | ConvertTo-Json -Depth 5

$responseCritical = Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8000/webhook" `
  -ContentType "application/json" `
  -Body $bodyCritical

$responseCritical
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/events/$($responseCritical.event_id)"
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/approvals"
Invoke-RestMethod -Method GET -Uri "http://localhost:8002/notifications"
```

## Monitoreo de logs

Logs de Warden:

```powershell
docker compose logs -f warden
```

Logs del mock de orquestador:

```powershell
docker compose logs -f orchestrator-mock
```

Logs del mock de notificaciones:

```powershell
docker compose logs -f notifier-mock
```

Ver los tres al mismo tiempo:

```powershell
docker compose logs -f
```

## Evidencia de uso de los mocks

Probar el mock del orquestador directamente:

```powershell
$body = @{
  project_id     = "demo-api"
  environment_id = "qa"
  event_id       = "manual-test-1"
  action         = "restart"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8001/actions" `
  -ContentType "application/json" `
  -Body $body
```

Probar el mock de notificaciones directamente:

```powershell
$body = @{
  type            = "approval_required"
  approval_id     = "approval-demo-1"
  event_id        = "event-demo-1"
  project_id      = "payments-api"
  environment_id  = "prod"
  proposed_action = "rollback"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8002/notify" `
  -ContentType "application/json" `
  -Body $body

Invoke-RestMethod -Method GET -Uri "http://localhost:8002/notifications"
```
