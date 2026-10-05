"""Candidatura asistida (fase 11): rellenar formularios de ATS y enviar solo tras tu confirmación.

- `platforms`: qué plataforma es (por la URL y, si no, mirando la página) y su URL de solicitud.
- `browser`: el navegador persistente del worker (`data/browser-profile/`), en su propio hilo.
- `guard`: captcha, anti-bot y login; y el bloqueo del envío mientras se rellena.
- `fields`: localizar los campos por su etiqueta accesible, decidir qué va en cada uno y rellenar.
- `tokens`: la confirmación de envío de un solo uso (`SubmitConfirmation`).
- `submit`: el único módulo que pulsa el botón de envío, y solo con una `SubmitConfirmation`.
- `service`: los intentos (`application_attempts`), las tareas del worker y los eventos.

No hay herramienta MCP ni comando `--json` para esto, a propósito (POLICIES §5): el envío solo se
desencadena desde la UI.
"""
