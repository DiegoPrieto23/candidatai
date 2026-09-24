# Fase 03 · Alta de ofertas por URL y por texto

## Contexto
Lee `docs/DATA_MODEL.md` (§jobs, §Huella) y `docs/POLICIES.md` §6.

## Objetivo
Poder meter ofertas a mano de forma fiable, sin duplicados y con las señales de riesgo detectadas
por el propio código (ADR-012), antes de que ningún agente las lea.

## Alcance
1. `app/services/ingest.py`:
   - `add_from_url(url)`: descarga con httpx (timeout, user-agent realista, sin cookies),
     extrae el texto principal con `trafilatura` y título/empresa con metadatos (JSON-LD
     `JobPosting` si existe, `og:` como alternativa).
   - Si la página exige login o devuelve poco texto (< 400 caracteres), no inventes: devuelve un
     error claro que sugiera `add_from_text`. Las URLs de LinkedIn van directamente por esa vía.
   - `add_from_text(title, company, text, url=None)`.
   - Ambas: normalizan, calculan la huella, detectan duplicados exactos (devuelven el existente)
     y difusos (`rapidfuzz`, umbral en `config/policies.yaml`), y registran el evento `found`.
2. Limpieza del texto: quitar navegación, cookies y pies; conservar listas; limitar a 20 000
   caracteres. No ejecutar JavaScript en esta fase.
3. CLI: `jh jobs add-url <url>`, `jh jobs add-text --title --company --file <ruta>` y
   `jh jobs list --stage`, todos con `--json`.
4. `app/services/untrusted.py`, detección de riesgo al guardar:
   - **texto oculto** en el HTML original: `display:none`, `visibility:hidden`, `font-size:0`,
     `opacity:0`, `aria-hidden` con texto, texto posicionado fuera de pantalla y color igual al
     fondo cuando sea detectable en estilos en línea;
   - **frases de inyección** en el texto limpio, con patrones multilingües en
     `config/injection_patterns.yaml` ("ignore previous instructions", "ignora las instrucciones
     anteriores", "if you are an AI", "si eres una IA", "as a language model"…), normalizando
     mayúsculas, acentos y espacios;
   - resultado en `jobs.risk_flags` y, si hay alguna, evento `injection_suspected` con actor
     `system` y un extracto de hasta 200 caracteres. La oferta se guarda igualmente: se avisa,
     no se censura.
5. Fixtures HTML en `backend/tests/fixtures/` con ofertas **inventadas**: una con JSON-LD, una sin
   él, una página de login, una con texto oculto (`display:none`) dirigido a una IA y otra con
   una frase de inyección visible en español.

## Fuera de alcance
Conectores de ATS, extracción con LLM.

## Criterios de aceptación
- Tests sin red (respx) para los cinco casos de fixture; los dos maliciosos acaban con
  `risk_flags` y evento `injection_suspected`, y los tres limpios sin falsos positivos.
- Añadir dos veces la misma oferta devuelve el mismo `job_id` y no crea eventos nuevos.
- Una variante con el título ligeramente distinto se marca `duplicate_of`.

## Al terminar
Actualiza `docs/ROADMAP.md` y propón mensaje de commit.
