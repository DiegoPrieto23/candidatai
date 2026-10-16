# Modelos gratuitos y locales

CandidatAI no llama a ningún modelo (ADR-001): el razonamiento lo hace tu agente. Esta guía explica
cómo usar la app **sin pagar por tokens**: con un modelo en tu equipo, con un modelo gratuito en la
nube o con la suscripción que ya tengas. Qué funciona con cada agente y modelo no sale de opiniones:
sale de la matriz medida con `cai eval compat` (ver «Comprobar que tu modelo da la talla» y
`evals/compat/REPORT.md`).

Nombres, tamaños y límites comprobados el **2026-10-16**. Cambian a menudo: si algo no cuadra,
mira la página que se enlaza en cada caso.

## Tres vías

| Vía | Coste | Privacidad | Límites | Con qué agente |
|---|---|---|---|---|
| **Local**: Ollama o LM Studio | Gratis (tu equipo y tu luz) | Nada sale de tu equipo | La memoria de tu equipo y la velocidad: un CV puede tardar minutos | OpenCode, Codex (`--oss`), Qwen Code |
| **En la nube, gratis**: modelos `:free` de OpenRouter, plan gratuito de Antigravity | Gratis | Las ofertas y tu perfil van al proveedor del modelo | OpenRouter: 20 peticiones por minuto y 50 al día (1 000 si alguna vez compraste 10 créditos). Antigravity: el cupo de tu cuenta de Google | OpenCode o Qwen Code con OpenRouter; Antigravity CLI |
| **Tu suscripción**: Claude, ChatGPT | Lo que ya pagas | Las ofertas y tu perfil van a Anthropic u OpenAI | Los de tu plan | Claude Code, Codex |

Los **niveles de gasto** de la página «Agente» combinan las tres vías. En «Económico», las acciones
cerradas (procesar ofertas, valorar el encaje, clasificar respuestas) usan un modelo local y el CV
usa tu agente más capaz. Ver «Niveles de gasto» más abajo.

## Qué sale de tu equipo

| | Local | Nube gratis | Tu suscripción |
|---|---|---|---|
| Texto de las ofertas | No | Sí, al proveedor del modelo | Sí, a Anthropic u OpenAI |
| Tu perfil (experiencia, skills, logros) | No | Sí | Sí |
| Tu correo, teléfono y mínimo salarial | No | No (1) | No (1) |
| Tus CVs y cartas ya generados | No | Solo si el agente los lee | Solo si el agente los lee |

(1) `get_profile` no devuelve el email, el teléfono ni la sección `private` (POLICIES §4). Un agente
con acceso a ficheros, en una sesión interactiva, *podría* leer `data/profile.yaml` si se lo pides.
En segundo plano (Claude Code y OpenCode, los únicos que lo tienen) no puede: solo lee `docs/`
(Claude Code) o nada (OpenCode). Ver «En segundo plano» en `docs/AGENTS_COMPAT.md`.

Con un proveedor gratuito en la nube, revisa su política: algunos guardan las peticiones o las usan
para entrenar. En OpenRouter, cada modelo dice qué hace su proveedor con los datos, y en tu cuenta
puedes bloquear los que entrenan con ellos.

## Ollama en Windows, paso a paso

1. **Instálalo** desde https://ollama.com/download (instalador para Windows). Queda en la bandeja del
   sistema y escucha en `http://127.0.0.1:11434`.
2. **Sube el contexto. Sin esto, los agentes no funcionan.** Ollama usa 4 096 tokens por defecto con
   menos de 24 GB de memoria de vídeo, y las instrucciones de un agente ya ocupan más. Los
   síntomas: respuestas cortadas, herramientas que no se llaman o un agente que «olvida» la
   orden.
   - Cierra Ollama desde la bandeja.
   - Ajustes de Windows → busca «variables de entorno» → «Editar las variables de entorno de esta
     cuenta».
   - Nueva variable: `OLLAMA_CONTEXT_LENGTH` = `32768` (o `65536` si tienes memoria de sobra).
   - Vuelve a abrir Ollama desde el menú Inicio, y reinicia CandidatAI para que el diagnóstico la vea.
   También se puede cambiar desde los ajustes de la app de Ollama (el control deslizante del
   contexto).
3. **Descarga un modelo** (ver la tabla de abajo), por ejemplo:
   ```powershell
   ollama pull gpt-oss:20b
   ```
4. **Comprueba** con `uv run --directory backend cai agents doctor`. La sección «Modelos locales
   (Ollama)» dice si responde, qué modelos tienes, su contexto y si algo no llega. Lo mismo sale en
   la tarjeta del agente de la página «Agente».

El diagnóstico solo lee metadatos (`/api/version`, `/api/tags` y `/api/show`). La app nunca pide a
Ollama que genere nada: lo hace tu agente.

**LM Studio** (https://lmstudio.ai) también vale: arranca su servidor (`http://127.0.0.1:1234/v1`) y
pon la longitud de contexto al cargar el modelo. El diagnóstico de la app solo conoce Ollama.

## Qué modelo, según tu memoria

Con memoria nos referimos a la de vídeo si tienes una gráfica dedicada, o a la RAM si no la tienes
(más lento). Etiquetas y tamaños de https://ollama.com/library:

| Memoria disponible | Modelo | Tamaño | Para qué |
|---|---|---|---|
| 8 GB | `qwen3:8b` | 5,2 GB | Solo para probar. **Los modelos de unos 8B o menos suelen fallar con los esquemas estrictos** (extracción, CV): campos inventados, JSON roto, herramientas sin llamar |
| 16 GB | `gpt-oss:20b` | 14 GB | Procesar ofertas y valorar el encaje. Admite herramientas y 128K de contexto. Con 16 GB de RAM y sin gráfica va justo y lento |
| 16 GB | `qwen3:14b` | 9,3 GB | Alternativa más ligera a la anterior, con 40K de contexto |
| 24 GB | `devstral:24b` | 14 GB | Agente de código con herramientas, 128K de contexto |
| 24 GB o más | `qwen3-coder:30b` | 19 GB | Lo más capaz de esta lista para agentes, 256K de contexto |

Para **redactar el CV**, mejor tu suscripción o el modelo más grande que tengas: la app avisa si
eliges un modelo de unos 8B o menos para `generate-cv`. Lo que dé la talla de verdad lo dice la
matriz, no esta tabla.

## Configurar cada agente con un modelo local

La configuración **personal** (proveedor, modelo, clave) va en la carpeta de usuario de cada agente,
**nunca** en los ficheros del repositorio: `opencode.json`, `.qwen/settings.json` y `.codex/` se
regeneran con `scripts/sync_agents.py` y no deben llevar nada tuyo.

### OpenCode
En `~/.config/opencode/opencode.json` (en Windows, `C:\Users\<tú>\.config\opencode\opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (local)",
      "options": { "baseURL": "http://localhost:11434/v1" },
      "models": { "gpt-oss:20b": { "name": "gpt-oss 20B" } }
    }
  }
}
```

En la app, el modelo de OpenCode se escribe `ollama/gpt-oss:20b` (proveedor/modelo). Las claves de
un proveedor en la nube (OpenRouter…) se añaden con `/connect` dentro de OpenCode y quedan en
`~/.local/share/opencode/auth.json`. **Los modelos gratuitos de OpenCode Zen no sirven**: rechazan
los agentes propios, y la app los usa en los subagentes y en segundo plano (ver
`docs/AGENTS_COMPAT.md`).

### Codex
El preset `local` de la app lanza `codex --oss -m gpt-oss:20b`, que usa Ollama. Elige el preset en
la tarjeta de Codex de la página «Agente». Con LM Studio, Codex necesita además
`--local-provider lmstudio`, que el preset no lleva: de momento, ábrelo tú desde la terminal.

### Qwen Code
Su plan gratuito con OAuth cerró el 15/04/2026. Configúralo en `~/.qwen/settings.json` con un
proveedor compatible con OpenAI (Ollama: `http://localhost:11434/v1`; OpenRouter; DashScope) según
https://qwenlm.github.io/qwen-code-docs/.

### Antigravity CLI
Usa los modelos de Google con tu cuenta, con el cupo del plan gratuito. No admite modelos locales.

## No pagar por API sin querer

Si en tu equipo hay una clave de API (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`…), algunos agentes la
usan en vez de tu suscripción y cobran por token. Los botones y el segundo plano de la app la
**quitan del entorno** antes de lanzar el agente: lo dice `launch.unset_env` de cada agente en
`.agents/manifest.yaml`. Si lanzas el agente tú, desde una terminal, la clave sigue ahí. Para no
depender de eso:

- no guardes claves de API en las variables de entorno de tu cuenta si no las usas;
- o abre el agente desde los botones de la app.

## Niveles de gasto

En la página «Agente», «Niveles de gasto» trae tres conjuntos de agente y modelo para las acciones
principales (procesar ofertas, valorar el encaje, clasificar respuestas y generar el CV):

- **Económico**: las cerradas con un modelo local (el primer agente instalado que los admite; si
  no tiene un preset local, escribe el modelo en «Editar»), y el CV con tu agente más capaz;
- **Equilibrado**: las cerradas con el modelo rápido de tu agente más capaz; el CV, con su modelo de
  siempre;
- **Máximo**: todo con tu agente más capaz.

Rellénalos una vez («Editar») y aplica uno con un clic. Aplicar cambia la tabla «Por acción».
«Deshacer el último» deja las preferencias como estaban. La propuesta sale de los agentes que
tienes instalados y del manifiesto, no de nombres escritos en el código.

## Comprobar que tu modelo da la talla

`cai eval compat` pasa la misma matriz a cualquier agente y modelo, sobre una demo propia con datos
ficticios. Tus datos de `data/` no se tocan.

```powershell
uv run --directory backend cai eval compat --agent opencode --model ollama/gpt-oss:20b
uv run --directory backend cai eval compat --agent codex --preset local
```

1. Crea `data-demo-compat-<agente>-<modelo>/` con las 5 ofertas de la matriz.
2. Lanza en segundo plano `process-jobs` y `assess-fit`.
3. Aprueba las 5 ofertas, solo en esa demo.
4. Lanza `generate-cv` de cada una.
5. Mide:
   - los campos de la extracción iguales a los esperados;
   - las valoraciones;
   - las 7 comprobaciones de `cai eval cv`;
   - el tiempo, los turnos y los tokens.

El resultado va a `evals/compat/results/` y el resumen, a `evals/compat/REPORT.md`.

Si el agente no puede hacer un paso en segundo plano (Codex, Qwen Code o Antigravity, y
`generate-cv` con OpenCode), el comando imprime los pasos manuales. Al acabarlos, `--import` mide lo
que hiciste. `--timeout <minutos>` da más tiempo por ejecución, útil con modelos locales lentos.
