# Fase 27 · Ayudas en los botones, prioridades únicas, varios buzones, experiencia plegable y preferencias de búsqueda

Rama `fase/27-mejoras-ui`. Cinco subfases, cada una con su encargo y su commit (o sus commits) en la
misma rama, en este orden: 27.1 → 27.2 → 27.3 → 27.4 → 27.5. **Una subfase por sesión.** Va después
de la 26. Petición del usuario (2026-10-23), tras usar la app en real.

## Antes de empezar
`mejora/fuentes-orden-logos-limite` (logos de empresas, «Ofertas por recorrido» y el orden de las
pestañas de Fuentes) ya está fusionada en `main` (`48da9d7`). La 27.3 parte de ese código: abre
`fase/27-mejoras-ui` desde `main` al día y comprueba con `git diff --ignore-space-at-eol --stat` que
no queda nada colgando.

## Contexto
Lee `docs/DECISIONS.md` ADR-024 y ADR-032 (botones que abren tu agente), ADR-016 y ADR-033 (qué
puede leer la app y qué no), ADR-026 (`require_ui`) y ADR-036 (UI en dos idiomas); `docs/FUENTES_OFERTAS.md`
(§Plataformas y §Alertas por correo), `docs/CONFIGURAR_CORREO.md`, y `docs/pruebas/PENDIENTES.md`.

## Objetivo
Cuatro mejoras de uso que salen de trabajar con la app a diario:

1. Que se entienda para qué sirve cada botón que lanza un skill, sin tener que probarlo.
2. Que en Fuentes → Plataformas no puedan coincidir dos prioridades.
3. Que Alertas lea más de un buzón y explique cómo conectar Gmail, Outlook y el resto.
4. Que «Mi perfil → Experiencia» se pueda recorrer de un vistazo (empresas plegadas) y que se vea
   dónde acaba cada empresa y cada logro.
5. Que «Mi perfil → Búsqueda» esté ordenado y tenga los filtros que faltan: años mínimos, sueldo
   mínimo, palabras que descartan, ofertas dudosas, tipo de contrato y tipo de empresa.

## Subfases
| | Encargo | Resultado visible |
|---|---|---|
| 27.1 | `prompts/27.1-ayudas-botones.md` | Al pasar el ratón (o enfocar con el teclado) por «Ampliar búsqueda» y por cualquier otro botón de un skill, un globo dice qué hace, qué toca y qué necesita |
| 27.2 | `prompts/27.2-experiencia-plegable.md` | «Experiencia» arranca con las empresas plegadas, se despliegan una a una, con bordes rectos y logros alternando fondo |
| 27.3 | `prompts/27.3-prioridades-unicas.md` | Las plataformas tienen un orden sin empates; elegir una prioridad ocupada las intercambia |
| 27.4 | `prompts/27.4-alertas-varios-buzones.md` | Botón «Añadir buzón» en Alertas, con guía integrada para Gmail, Outlook, Yahoo, iCloud y otros |
| 27.5 | `prompts/27.5-preferencias-busqueda.md` | «Búsqueda» en bloques y con los campos alineados, con años mínimo y máximo, sueldo mínimo (privado), palabras que descartan, tipo de contrato y de empresa y ofertas dudosas |

El orden va de menos a más riesgo: 27.1 y 27.2 son solo frontend; 27.3 toca el esquema de fuentes;
27.4 toca la lectura de correo y la seguridad de las credenciales; 27.5 toca el perfil, la
extracción y los filtros duros, y la privacidad del sueldo.

## Decisiones propuestas (confirmar con el usuario antes de la subfase indicada)
- **27.3 · Intercambio, no rechazo.** El servidor rechaza un empate como red de seguridad, pero la
  UI no deja llegar a ese error: elegir un número ocupado intercambia las dos plataformas.
- **27.3 · La prioridad pasa a ser un puesto (1…N).** Hoy es `1..10` con valor por defecto 5, así que
  todas las plataformas nuevas empatan y, con más de 10, la unicidad es imposible. Se quita el tope
  de 10, el valor por defecto es «la última» y una migración de datos reordena lo que haya.
- **27.4 · Dónde viven las contraseñas.** Recomendado: **seguir solo en `.env`** (es lo que dice la
  política hoy, funciona igual en Docker y no entra en git). La UI guarda lo no secreto (etiqueta,
  servidor, usuario, carpeta) en la base de datos y escribe la línea de la contraseña en `.env`
  ella misma, con un fichero temporal y permisos del usuario. Alternativas: llavero del sistema
  (más seguro, pero no existe en Docker ni en algunos Linux) o pedir al usuario que pegue él la
  línea (más simple, peor experiencia). **Es una decisión de seguridad: va a un ADR nuevo.**
- **27.4 · Outlook.** Microsoft ya no permite IMAP con contraseña en cuentas personales ni de
  trabajo (exige OAuth). La app no va a implementar OAuth en esta fase; la guía ofrece el camino
  práctico (una regla en Outlook que reenvíe las alertas a una cuenta de Gmail, o exportar `.eml` a
  `data/inbox/`). Habrá que **comprobar el estado real en la documentación oficial al escribirla**.

- **27.5 · Ya confirmadas** (2026-10-23): mínimo de años como filtro duro; sueldo mínimo como
  filtro duro sin que el agente vea nunca la cifra; las palabras que descartan pasan al perfil; tipo
  de contrato y tipo de empresa (campo nuevo `employer_kind` en la extracción). Detalle en su
  encargo. **El sueldo va a un ADR nuevo.**

## Fuera de alcance
OAuth con Google o Microsoft, enviar correo desde la app (sigue sin enviar nada), reordenar
plataformas arrastrando, y traducir a más idiomas (siguen siendo español e inglés).

## Criterios de aceptación de la fase
- Cada botón de skill de la UI tiene su ayuda en español e inglés, y un test falla si se añade una
  acción sin ayuda.
- No se puede guardar ninguna plataforma con una prioridad repetida, ni desde la UI, ni con la CLI
  (`cai sources …`), ni con MCP (`save_source`); los datos existentes quedan sin empates tras migrar.
- Alertas lee de todos los buzones activos, sin duplicar ofertas que lleguen por dos de ellos, y la
  contraseña no sale nunca por la API ni por MCP.
- «Experiencia» arranca plegada y no pierde cambios sin guardar al plegar y desplegar.
- «Búsqueda» no tiene campos descuadrados, sus filtros nuevos funcionan y la cifra del sueldo no
  sale nunca por la interfaz para agentes.
- Tests de backend y frontend en verde, ruff limpio, `sync_agents.py --check` en verde, `pnpm build`
  sin avisos, `docs/ROADMAP.md`, `docs/RESUMEN_FASES.md`, `CHANGELOG.md`, `docs/GUIA.md` y
  `docs/GUIDE.md` (las dos guías, por la regla de paridad) y `docs/pruebas/PENDIENTES.md` al día.
