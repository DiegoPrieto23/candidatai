# Fase 24.6 · Pasar la matriz de compatibilidad

Objetivo: medir con `cai eval compat` qué agente y qué modelo dan la talla en `process-jobs`,
`assess-fit` y `generate-cv`, sobre las mismas 5 ofertas ficticias. Los resultados quedan en
`evals/compat/results/` y en `evals/compat/REPORT.md`, y con ellos se completan
`docs/AGENTS_COMPAT.md`, el README y la ADR-037.

Cada pasada usa su propia demo (`data-demo-compat-<agente>-<modelo>/`, ignorada por git). Tus datos
de `data/` no se tocan. Mínimo: **Claude Code con MCP** y, para cerrar la fase 24, **OpenCode con un
modelo local**. Codex, OpenCode con un modelo gratuito en la nube, Qwen Code y Antigravity, si los
tienes.

## Antes de empezar

- Arranca desde la raíz del repo, en la rama `fase/24-multiagente`, con `uv sync --directory backend`
  hecho.
- **No hace falta `cai worker`:** `cai eval compat` ejecuta el agente él mismo, de una en una.
- Cierra cualquier sesión de tu agente abierta en este repo.
- `uv run --directory backend cai agents doctor`: el agente que vas a probar sale como instalado.

## 1. Claude Code con MCP (unos 30-40 minutos; usa tu suscripción)

```powershell
uv run --directory backend cai eval compat --agent claude
```

Va solo: extrae, valora, aprueba y genera los 5 CVs en segundo plano. Al acabar imprime el resumen
y deja el resultado. Si una ejecución agota el tiempo, repite con `--timeout 30` (minutos).

Si quieres verlo en la UI mientras tanto: en otra terminal, `$env:CAI_DATA_DIR =
"data-demo-compat-claude-default"` y `uv run --directory backend cai serve`. Después,
http://127.0.0.1:8000/agente.

## 2. OpenCode con Ollama (lo que cierra la fase 24)

1. Monta Ollama según `docs/MODELOS_GRATIS.md`:
   - `OLLAMA_CONTEXT_LENGTH=32768`;
   - `ollama pull gpt-oss:20b`, o `qwen3:14b` si `gpt-oss` no te cabe en la memoria.
2. Instala OpenCode (`npm install -g opencode-ai`) y configura el proveedor `ollama` en
   `~/.config/opencode/opencode.json`, como dice la guía.
3. `uv run --directory backend cai agents doctor`: Ollama responde, el modelo aparece y no hay aviso
   de contexto.
4. Lanza:
   ```powershell
   uv run --directory backend cai eval compat --agent opencode --model ollama/gpt-oss:20b --timeout 30
   ```
   `process-jobs` y `assess-fit` van en segundo plano. `generate-cv` no puede ir en segundo plano
   con OpenCode, así que el comando para ahí e imprime los pasos manuales: abre OpenCode con
   `CAI_DATA_DIR` apuntando a la demo, pídele el skill `generate-cv` con los 5 ids y, al acabar,
   `--import`.
   - Si prefieres medir solo las acciones cerradas, ejecuta `--import` sin generar los CVs: la
     extracción y las valoraciones quedan medidas, y el CV como pendiente.

## 3. Codex (sin segundo plano: a mano)

```powershell
uv run --directory backend cai eval compat --agent codex                 # tu cuenta de ChatGPT
uv run --directory backend cai eval compat --agent codex --preset local  # gpt-oss:20b con Ollama
```

Imprime los pasos:

1. abrir Codex con `CAI_DATA_DIR`;
2. `$process-jobs` y `$assess-fit`;
3. `… --approve`;
4. `$generate-cv` con los ids;
5. `… --import`.

## 4. OpenCode con un modelo gratuito en la nube

Con una clave de OpenRouter (`/connect` en OpenCode) y un modelo `:free` con herramientas. Los
gratuitos de OpenCode Zen **no sirven**: rechazan los agentes propios.

```powershell
uv run --directory backend cai eval compat --agent opencode --model openrouter/<modelo>:free
```

OpenRouter permite 50 peticiones al día en los modelos gratuitos, y una pasada puede gastarlas.
Si se corta, apúntalo: también es un resultado.

## 5. Qwen Code o Antigravity, si los tienes

Igual que Codex: a mano, con `--approve` e `--import`.

## Qué apuntar

En cada pasada:

- lo que imprime al final (o el JSON de `evals/compat/results/`);
- los permisos que te pidió el agente;
- si alguna ejecución falló, su error, que sale en la página «Agente» de la demo y en el JSON.

Pásame `evals/compat/REPORT.md`. Con eso:

- se rellena la columna de cada agente en `docs/AGENTS_COMPAT.md`;
- se pone «probado» en la tabla del README;
- se cierra la decisión de la ADR-037 sobre la ADR-001: solo se revisaría si ningún agente con un
  modelo local supera las acciones cerradas.

## Al terminar

Las carpetas `data-demo-compat-*` se pueden borrar. Los resultados de `evals/compat/results/` y el
informe se quedan en el repositorio.
