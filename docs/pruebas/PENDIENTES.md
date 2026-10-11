# Pendientes del usuario

Cosas que tiene que hacer el usuario a mano: el agente no puede hacerlas (permisos, cuentas,
navegador, Claude Code cerrado) o necesitan datos reales. El agente añade aquí lo que salga en
cada fase y lo quita cuando el usuario confirma que está hecho.

Marca `[x]` lo que hagas y, si algo falla, apúntalo debajo de la línea con `→`.

Última actualización: 2026-10-12 (fase 15).

## 1. Poner la app al día (antes de probar nada)

Desde la raíz del repo, en PowerShell, en `main` y **con Claude Code cerrado** (su servidor MCP
bloquea el entorno de Python):

- [ ] Copia de seguridad de la BD: `copy data\jobhunter.db data\jobhunter.db.bak-0012`
- [ ] `uv sync --directory backend` (dependencias añadidas con `--no-sync`, p. ej. `tzdata`)
- [ ] `uv run --directory backend jh db upgrade`: tu BD está en **0012** y el código espera la
      **0014** (`skill_gap_marks` de la fase 14; `replies` y `message_drafts` de la 15)
- [ ] `cd frontend; pnpm install`
- [ ] Abrir Claude Code de nuevo para que el servidor MCP cargue las herramientas nuevas
      (`list_replies`, `get_reply`, `save_reply_proposal`, `save_message_draft`, `get_skill_gaps`…).
      Comprobar con `/mcp`.

## 2. `.env.example` (el agente no puede leerlo ni editarlo)

- [ ] Crear o completar `.env.example`, **sin valores reales**, con todas las variables de
      `backend/app/core/config.py`:
  - generales: `JH_DATA_DIR`, `JH_DB_URL`, `SOFFICE_PATH`, `JH_CLIENT_NAME`, `JH_AGENT`,
    `JH_EMBEDDINGS`;
  - portales: `JH_INFOJOBS_CLIENT_ID`, `JH_INFOJOBS_CLIENT_SECRET`, `JH_ADZUNA_APP_ID`,
    `JH_ADZUNA_APP_KEY`;
  - correo: `JH_IMAP_HOST`, `JH_IMAP_PORT`, `JH_IMAP_USER`, `JH_IMAP_PASSWORD`,
    `JH_IMAP_FOLDER` y, de la fase 15, `JH_IMAP_REPLIES_FOLDER` (por defecto `INBOX`);
  - navegador: `JH_CAPTURE_EXTENSION_ID`, `JH_BROWSER_HEADLESS`, `JH_BROWSER_CHANNEL`,
    `JH_APPLIER_ALLOW_LOOPBACK`.

## 3. Pruebas manuales pendientes

Cada guía está en `docs/pruebas/`. No consta en el ROADMAP que estén hechas; si alguna ya la
hiciste, márcala.

- [ ] **Fase 15 · Respuestas y seguimientos** (`fase-15-prueba-manual.txt`):
  - IMAP real sobre `INBOX`: `jh doctor` en verde y «Revisar correo ahora» en «Respuestas»;
  - pantalla «Respuestas» y aviso en la ficha en el navegador (Aceptar, Cambiar, Ignorar);
  - `/revisar-respuestas` y `/redactar-seguimiento` con tus candidaturas;
  - sección «Borradores» (copiar, «Ya lo he enviado», «Descartar»).
- [ ] **Fase 14 · Skills**: página «Skills» con datos reales (alias, marcas, recálculo del
      worker), «Añadir al perfil las que tengo» y `plan-formacion` (web y escritura de
      `data/documentos/plan-formacion.md`).
- [ ] **Fase 13 · Contexto y documentos**: la UI en el navegador (solo se probó con tests).
- [ ] **Fase 12 · Compatibilidad**: Claude Code con MCP sobre la matriz
      (`fase-12-compatibilidad.txt`).
- [ ] **Fase 11 · Candidatura asistida** (`fase-11-prueba-manual.txt`): una oferta real de
      Greenhouse o Lever hasta la pantalla de revisión, **sin enviar** (sobre todo los desplegables
      con buscador de Greenhouse), y ofertas reales de cada portal.
- [ ] **Fases 08 a 10**: hay una lista única en `fases-08-10-resumen-pruebas.txt` (5,5-6 h, por
      bloques). Incluye:
  - CV con un CV real (08b, parte 4) y carta (08c: `/generar-carta`, PDF a juego, DOCX en Word);
  - conectores con tus empresas objetivo (09);
  - extensión «Enviar a Job Hunter» con LinkedIn y otros portales (09b; los selectores se
    escribieron sin páginas reales);
  - `buscar-ofertas configurar` y un recorrido con Claude in Chrome (09b.3);
  - arrastre del kanban e importación del `.ics` en Google Calendar (10.1), dashboard (10.2:
    < 1 s, modo oscuro, móvil) y paquete de candidatura (10.3).
- [ ] **Uso real**: el plan de `uso-real-plan.txt`, con los hallazgos en
      `docs/pruebas/uso-real-hallazgos.txt` (aún no existe).

## 4. Fuera de la app

- [ ] **Codex**: cuando lo instales, parte 3 de la guía de la fase 04 y actualizar
      `docs/AGENTS_COMPAT.md`.
- [ ] **CI en GitHub**: comprobar que pasa el paso de la fase 12 (en local solo se probó con
      LibreOffice; en CI va con Chromium). Requiere hacer push.
- [ ] **Contraseña de aplicación de Gmail**: si la creaste para las alertas, sirve también para
      las respuestas. Revócala si dejas de usar la app.
