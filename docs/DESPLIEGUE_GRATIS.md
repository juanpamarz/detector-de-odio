# Despliegue gratuito 24/7 sin tu computadora

## Por qué el bot hoy necesita tu PC encendida

Con `docker compose` hay procesos que **esperan** todo el tiempo: el gateway pregunta a Telegram si hay mensajes nuevos (long-polling) y los workers de Celery esperan tareas en RabbitMQ. Si apagas la PC, nadie pregunta ni procesa.

La solución es invertir el flujo: que **Telegram avise** cuando hay un mensaje (webhook) y que cada mensaje despierte una función en la nube solo durante el tiempo que tarda en procesarse.

## Opción recomendada: serverless y distribuido, sin tarjeta

```
Telegram ──webhook──> Vercel: /api/telegram/webhook  (valida y encola, ~100 ms, termina)
                              │
                              ▼
                       Upstash QStash  (cola gestionada: reintentos con backoff exponencial,
                              │          deduplicación, entrega en paralelo)
                              ▼
          Vercel: /api/internal/tasks/process_message   ×N invocaciones en paralelo
                 (worker: modelos de IA con respaldo, borra, avisa, registra)
                              │
                              ▼
                     Neon PostgreSQL (serverless)  <──  Panel React en Vercel
```

Sigue siendo un sistema distribuido: el receptor y los workers están desacoplados por una cola, y cada mensaje se procesa en una instancia independiente que escala de 0 a N sola. La diferencia con Celery es que nadie espera encendido: QStash *empuja* cada tarea al worker por HTTPS y lo despierta.

| Servicio | Para qué | Capa gratuita (verifica antes de usar, cambian seguido) |
|---|---|---|
| Vercel (Hobby) | API, webhook, workers y panel | Funciones serverless; uso no comercial |
| Upstash QStash | Cola de mensajes con reintentos | 1,000 mensajes al día (un mensaje del grupo es una tarea) |
| Neon | PostgreSQL | 1 GB por proyecto; se suspende tras 5 min sin uso y despierta solo |

Ninguno pide tarjeta de crédito. Con 1,000 tareas al día alcanza para la presentación y para varios grupos pequeños. Si un grupo es muy activo, revisa el consumo en el panel de Upstash.

### Lo que necesitas (solo cuentas, todo gratis)

1. Cuenta de **GitHub** y el proyecto subido a un repositorio (puede ser privado). **No subas `.env`**: ya está en `.gitignore`.
2. Cuenta de **Vercel** (entra con GitHub).
3. Cuenta de **Neon** (neon.com, entra con GitHub o Google).
4. Cuenta de **Upstash** (upstash.com, entra con GitHub o Google).
5. Al menos una clave de modelo de IA (abajo la lista); con dos o más ya hay respaldo.

### Paso 1. Base de datos en Neon (3 min)

1. Crea un proyecto llamado `centinela` y elige la región más cercana (por ejemplo, US East).
2. En **Connect**, activa **Connection pooling** y copia la cadena. Se ve así:
   `postgresql://usuario:clave@ep-xxxx-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require`
3. Guárdala: será `DATABASE_URL`. Las tablas se crean solas en el primer arranque (`AUTO_MIGRATE=true`).

Si quieres pasar tus datos actuales (los 76 registros de la v1 y los grupos demo), con Docker abierto en tu PC:

```powershell
$env:NEON="postgresql://...tu cadena..."
docker compose run --rm -e DATABASE_URL=$env:NEON migrate
docker compose run --rm -e DATABASE_URL=$env:NEON -v ${PWD}/moderacion_bot.db:/data/v1.db:ro api cli import-sqlite --path /data/v1.db
docker compose run --rm -e DATABASE_URL=$env:NEON api cli seed-demo     # opcional
```

### Paso 2. Cola en Upstash QStash (2 min)

En la consola de Upstash, abre **QStash** y copia tres valores: `QSTASH_TOKEN`, `QSTASH_CURRENT_SIGNING_KEY` y `QSTASH_NEXT_SIGNING_KEY`. Si la consola muestra un `QSTASH_URL` regional, cópialo también.

### Paso 3. Backend en Vercel (5 min)

1. En Vercel: **Add New → Project**, importa tu repositorio.
2. **Root Directory**: `backend`. Vercel detecta FastAPI solo (archivo `index.py`); no cambies los comandos de build.
3. En **Environment Variables** agrega:

| Variable | Valor |
|---|---|
| `DATABASE_URL` | la cadena de Neon |
| `AUTO_MIGRATE` | `true` |
| `QUEUE_BACKEND` | `qstash` |
| `QSTASH_TOKEN`, `QSTASH_CURRENT_SIGNING_KEY`, `QSTASH_NEXT_SIGNING_KEY` | los de Upstash |
| `PUBLIC_BASE_URL` | la URL que Vercel le dará al proyecto, p. ej. `https://centinela-api.vercel.app` (si aún no la sabes, despliega una vez, cópiala, agrégala y vuelve a desplegar) |
| `TELEGRAM_BOT_TOKEN` | el de BotFather |
| `TELEGRAM_WEBHOOK_SECRET` | una frase aleatoria (solo letras, números, `_` y `-`) |
| `JWT_SECRET` | otra frase aleatoria de 32+ caracteres |
| `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_PASSWORD`, `FIRST_ADMIN_NAME` | tu cuenta del panel |
| `CORS_ORIGINS` | la URL del panel (paso 4), p. ej. `https://centinela.vercel.app` |
| `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `OPENROUTER_API_KEY`, `EDENAI_API_KEY` | las claves de IA que tengas |
| `NLP_PROVIDERS` | `groq,cerebras,openrouter,edenai` |
| `NLP_ENSEMBLE_SIZE` | `3` |
| `APP_ENV` | `production` |

4. **Deploy**. Comprueba que `https://TU-API.vercel.app/api/health/ready` responda `{"status":"ok"}`.

> **Usa el dominio de producción, no la URL larga del despliegue.** Vercel muestra dos direcciones: la del proyecto (en **Settings → Domains**, p. ej. `https://proyectate-api.vercel.app`) y una por cada despliegue (`https://proyectate-api-a1b2c3-juanpablo.vercel.app`). Las largas están protegidas con inicio de sesión de Vercel: si pones una de esas en `PUBLIC_BASE_URL`, Telegram y QStash recibirán un 401 y el bot no hará nada.

### Paso 4. Panel en Vercel (3 min)

1. **Add New → Project**, mismo repositorio, **Root Directory**: `frontend`. Vercel detecta Vite.
2. Variable de entorno: `VITE_API_URL` = `https://TU-API.vercel.app/api`
3. **Deploy**. Agrega la URL que te asigne a `CORS_ORIGINS` del backend y vuelve a desplegar el backend.

### Paso 5. Conectar Telegram y apagar tu PC

1. **Apaga el bot local** (`docker compose down`): Telegram entrega a webhook *o* a polling, no a ambos.
2. Entra al panel, ve a **Grupos** y pulsa **Conectar webhook**. El recuadro de estado debe mostrar "Recibe mensajes por webhook".
3. En cada grupo escribe `/registrar`. El bot responde con sus permisos y el grupo aparece en el panel.
4. Escribe un mensaje ofensivo de prueba. En segundos debe borrarse y verse en **Incidentes**. En la consola de Upstash (QStash → Logs) verás cada tarea entregada y sus reintentos.

Desde aquí ya no necesitas tu computadora: cada `git push` a GitHub vuelve a desplegar todo automáticamente.

## Alternativa: una máquina virtual siempre encendida (misma arquitectura de Celery)

Si prefieres mostrar RabbitMQ + Celery funcionando tal cual, renta una VM gratuita y corre el mismo `docker compose up -d`. Con el gateway de polling no necesitas dominio ni HTTPS para el bot.

- **Oracle Cloud Always Free**: VMs ARM gratuitas de forma permanente; pide tarjeta solo para verificar identidad.
- **GitHub Student Developer Pack**: con tu correo de la UAQ incluye créditos en proveedores de nube (por ejemplo, DigitalOcean). Revisa las ofertas vigentes en education.github.com/pack.

Pasos: crea la VM (Ubuntu), instala Docker (`curl -fsSL https://get.docker.com | sh`), clona el repositorio, copia tu `.env` y ejecuta `docker compose up -d --build`. Para ver el panel abre el puerto 8080 en el firewall de la VM o usa un túnel de Cloudflare.

## Modelos de IA en cadena de respaldo

El orden de `NLP_PROVIDERS` es la prioridad. El bot consulta en paralelo los primeros `NLP_ENSEMBLE_SIZE` disponibles. Si uno falla por límite de uso (429), caída o clave inválida, toma el siguiente de la lista y deja al que falló en espera unos minutos. Dentro de cada proveedor, `*_MODEL` acepta varios modelos separados por comas: si uno desaparece o llega a su límite, se prueba el siguiente. Si fallan todos, deciden las reglas léxicas, que siempre están activas para sexismo, LGBTfobia, racismo, amenazas y crisis.

| Proveedor | Variable de clave | Dónde se obtiene | Modelos por defecto |
|---|---|---|---|
| Groq | `GROQ_API_KEY` | console.groq.com (gratis) | `openai/gpt-oss-120b`, `llama-3.1-8b-instant` |
| Cerebras | `CEREBRAS_API_KEY` | cloud.cerebras.ai (gratis) | `gpt-oss-120b`, `llama3.1-8b` |
| OpenRouter | `OPENROUTER_API_KEY` | openrouter.ai (modelos `:free`, ~50 peticiones al día) | `google/gemma-4-26b-a4b-it:free` |
| Eden AI | `EDENAI_API_KEY` | edenai.co (consume créditos; va al final) | `cohere/command-a-03-2025` |

Los nombres de modelo cambian con el tiempo; si un proveedor responde "modelo no encontrado", cambia su variable `*_MODEL`. En **Grupos → Estado del bot** ves la cadena en orden y cuáles están en espera; en **Probar mensajes**, qué respondió cada uno.
