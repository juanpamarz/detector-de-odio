# Centinela v2 — moderación distribuida de grupos de Telegram

Bot que cuida la convivencia en grupos de Telegram: retira en segundos mensajes con odio, acoso o amenazas, deriva a apoyo privado a quien expresa ideas de autolesión y deja un registro auditable que se explora en un panel web.

Conserva la lógica de la primera versión (crisis con mensaje privado, advertencias, botones «Retirar / Publicar de todos modos», expulsión al acumular faltas) y la lleva a una arquitectura distribuida que corre en local con `docker compose` o en la nube sin servidores encendidos.

## Para qué sirve (y cómo presentarlo)

- **Problema.** Los grupos escolares, vecinales y deportivos son espacios donde el ciberacoso y el discurso de odio se normalizan; quien administra no puede leer todo en tiempo real y los mensajes de crisis pasan desapercibidos entre cientos de mensajes.
- **Qué aporta.** (1) Intervención inmediata y pedagógica: el autor recibe un aviso de reflexión y puede retirar su mensaje (el panel mide esa «tasa de reconsideración»). (2) Prevención: los mensajes de riesgo de autolesión se retiran del grupo para proteger la privacidad y la persona recibe la Línea de la Vida (800 911 2000) en privado. (3) Evidencia: cada decisión queda registrada con puntajes por modelo, lo que permite auditar sesgos y falsos positivos.
- **Valor analítico.** Series por hora/día, distribución por tipo de daño, grupos más expuestos, personas reincidentes y un mapa de calor día x hora que indica cuándo conviene moderación humana.

## Arquitectura

```
                 ┌──────────── webhook (nube) ─────────────┐
Telegram ────────┤                                          ▼
                 └── long-polling (local) ── gateway ──> RabbitMQ / Redis ──> workers Celery ×N
                                                │                               │  ensamble NLP asíncrono
                                          FastAPI (API)                         │  (Groq, Cerebras, OpenRouter,
                                                │                               │   Eden AI, reglas léxicas)
React + TS + Tailwind  ── /api ──>  JWT + roles │                               │  borra / avisa / expulsa
(Framer Motion, Recharts, D3)                   └──────────> PostgreSQL <────────┘  (SQLAlchemy + Alembic)
```

- **Desacoplamiento.** El receptor (webhook o gateway) solo valida y **encola**; responde a Telegram en milisegundos. Todo lo lento ocurre en los workers.
- **NLP robusto.** Proveedores intercambiables detrás de un protocolo (`app/nlp/base.py`). Estrategia `ensemble` (media ponderada en paralelo con `asyncio.gather`) o `cascade` (el primero que responda). Reintentos con **backoff exponencial con jitter** (tenacity) ante 5xx/timeouts; si todos fallan, deciden las reglas léxicas. La heurística de crisis corre siempre como red de seguridad.
- **Umbrales configurables.** Globales por variable de entorno y **por grupo desde el panel**.
- **Idempotencia.** `(grupo, mensaje)` es único: los reintentos de Celery no duplican advertencias.
- **Privacidad.** Los textos de crisis se guardan redactados (`STORE_CRISIS_TEXT=false`).

### Modelos de IA

| Orden | Proveedor | Costo | Dónde obtener la clave |
|---|---|---|---|
| 1 | Groq (`openai/gpt-oss-120b`, respaldo `llama-3.1-8b-instant`) | Gratis | console.groq.com |
| 2 | Cerebras (`gpt-oss-120b`) | Gratis | cloud.cerebras.ai |
| 3 | OpenRouter (modelos `:free`, unas 50 peticiones al día) | Gratis | openrouter.ai |
| 4 | Eden AI | Créditos de pago | edenai.co |
| — | Reglas léxicas propias | — | Siempre activas para identidad, amenazas y crisis |

Todos usan la API compatible con OpenAI: agregar otro proveedor es una línea en `OPENAI_COMPATIBLE` (`app/nlp/engine.py`). Con una sola clave ya funciona. El bot consulta en paralelo los primeros `NLP_ENSEMBLE_SIZE` modelos disponibles de `NLP_PROVIDERS`; si uno falla (límite de uso, caída, clave inválida), pasa al siguiente y deja al que falló en espera unos minutos. Si fallan todos, deciden las reglas léxicas.

## Lo que necesitas hacer tú

1. **Docker Desktop** instalado y abierto (Windows).
2. **BotFather**: envía `/setprivacy` → elige tu bot → `Disable`. Sin esto el bot solo ve comandos, no los mensajes del grupo. Después **saca y vuelve a agregar** el bot al grupo.
3. En cada grupo, haz al bot **administrador** con permisos de *borrar mensajes* y *banear usuarios*.
4. Copia `.env.example` como `.env` y completa el token del bot, las claves de IA, `JWT_SECRET`, `FIRST_ADMIN_EMAIL` y `FIRST_ADMIN_PASSWORD`.

## Arranque local

```powershell
cd PROYECTATE
docker compose up -d --build

# Opcional: importar los registros de la primera versión (SQLite)
docker compose run --rm -v ${PWD}/moderacion_bot.db:/data/v1.db:ro api cli import-sqlite --path /data/v1.db

# Opcional: datos sintéticos para la presentación (6 grupos demo, 30 días)
docker compose run --rm api cli seed-demo
```

- Panel: <http://localhost:8080> (entra con `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD`)
- API y documentación OpenAPI: <http://localhost:8000/api/docs>
- RabbitMQ: <http://localhost:15672> (guest / guest)
- Más workers: `docker compose up -d --scale worker=3`
- Logs JSON: `docker compose logs -f worker`

Desarrollo del frontend con recarga en caliente: `cd frontend && npm install && npm run dev` (abre <http://localhost:5173>, usa la API del contenedor).

Despliegue 24/7 sin tu computadora: **[docs/DESPLIEGUE_GRATIS.md](docs/DESPLIEGUE_GRATIS.md)**. Usa Vercel con funciones serverless, Upstash QStash como cola y Neon como PostgreSQL; todo es gratis y sin tarjeta.

### Dos modos de cola, el mismo código

| `QUEUE_BACKEND` | Receptor | Cola | Workers | Uso |
|---|---|---|---|---|
| `celery` | gateway por polling o webhook | RabbitMQ | procesos Celery 24/7 | `docker compose`, VM |
| `qstash` | webhook en Vercel | Upstash QStash | funciones serverless que escalan de 0 a N | nube gratuita |

### Por qué un grupo no aparece en el panel

Telegram no permite que un bot liste sus grupos: cada grupo se registra cuando llega algo desde él. Puede ser al agregar o promover al bot, cuando alguien escribe (requiere el modo privacidad desactivado en BotFather), al usar el comando **`/registrar`** dentro del grupo (funciona incluso con el modo privacidad activado y el bot responde con sus permisos), o al agregarlo a mano en **Grupos** con su ID o `@usuario`. El panel muestra además si el bot es administrador, si puede borrar y expulsar, y si el modo privacidad le impide leer mensajes.

## Panel

- **Inicio de sesión** con un ojo vigilante: sigue el puntero, recorre el correo mientras escribes, se cierra al teclear la contraseña, se entreabre si la muestras, niega ante un error y dilata la pupila al entrar.
- **Panorama**: indicadores (tasa por mil mensajes, variación contra el periodo previo, tasa de reconsideración), serie temporal apilada con área sombreada por hora/día, dona multicapa (macrocategoría → subcategoría, D3), barras horizontales apiladas de personas y grupos, mapa de calor día x hora.
- **Grupos**: lista con tasa normalizada; detalle por grupo con sus propias figuras, ajuste de umbral, pausa de moderación y registro filtrable.
- **Incidentes**: tabla paginada con búsqueda, filtros por macrocategoría, acción, puntaje mínimo y fechas, panel lateral con el veredicto de cada modelo, exportación **CSV** (Excel) y **PDF** con los mismos filtros.
- **Cuentas del panel** (solo administración): roles `admin`, `moderator`, `analyst`.
- Modo claro/oscuro nativo (sigue al sistema, con selector), sin emojis, Source Serif 4 + IBM Plex Sans, figuras numeradas con pie de figura y respeto a «reducir movimiento».

## Estructura

```
backend/
  app/core/          config (pydantic-settings), logging JSON, seguridad (bcrypt + JWT)
  app/domain/        taxonomía de daño y contratos de mensajes de la cola
  app/db/            modelos SQLAlchemy 2 (3FN) y sesión
  app/nlp/           protocolo, proveedores, reintentos, motor de ensamble
  app/services/      política, caso de uso de moderación, analítica, exportes
  app/telegram/      cliente Bot API, dispatcher (encolado), gateway de polling
  app/workers/       cola intercambiable (Celery o QStash) y tareas
  app/api/           FastAPI: auth, analytics, groups, incidents, exports, bot, webhook, workers HTTP
  alembic/           migraciones
  tests/             pruebas de la lógica pura (pytest)
frontend/            React 18 + TypeScript estricto + Tailwind + Framer Motion + Recharts + D3
docs/                guía de despliegue gratuito
```

Pruebas: `cd backend && pip install -r requirements-dev.txt && pytest`. Tipado: `mypy app` y `npm run typecheck`.

## Sobre WhatsApp

Moderar grupos de WhatsApp existentes sin que haya un bot dentro no es viable de forma legítima: la API oficial (WhatsApp Business Platform) no lee los mensajes de grupos ajenos, y las librerías no oficiales que automatizan WhatsApp Web violan los términos de servicio y pueden provocar el bloqueo del número. Meta ofrece una Groups API dentro de la Cloud API, pero está pensada para grupos que crea la propia empresa, no para moderar comunidades ya formadas. Por eso Telegram es la elección correcta para la entrega; el diseño deja la puerta abierta: el dispatcher convierte cada evento a un `IncomingMessage` neutro, así que un canal nuevo solo necesita su propio adaptador de entrada y de acciones.

## Limitaciones y ética

- Los modelos cometen errores, sobre todo con ironía, albures y lenguaje reapropiado por comunidades. El panel conserva el veredicto de cada modelo para revisarlos y el umbral es ajustable por grupo.
- El bot no sustituye la atención profesional; ante una crisis comparte recursos y protege la privacidad, nada más.
- Informa a los miembros del grupo que hay moderación automatizada y qué se registra.
