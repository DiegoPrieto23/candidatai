# Enviar a Job Hunter

Extensión mínima para navegadores Chromium (Chrome, Edge, Brave) que envía la oferta que estás
viendo a tu Job Hunter local con un clic. Detalle y límites en `docs/FUENTES_OFERTAS.md`
§Botón «Enviar a Job Hunter».

- **Solo actúa cuando pulsas su botón**, en la pestaña actual. No se queda cargada en ninguna web,
  no lee cookies, no recorre páginas ni lee nada en segundo plano.
- Permisos: `activeTab`, `scripting` y `storage`. Solo puede hablar con `http://127.0.0.1:8000`.
- Lee la página que ya tienes delante: el texto que hayas seleccionado o, si no hay selección, la
  oferta (extractores para LinkedIn, InfoJobs, Indeed y Tecnoempleo; JSON-LD `JobPosting`; `main`).
- Si la oferta ya estaba como resumen de una alerta, la completa; si ya estaba completa, te lo
  dice; si no, la da de alta.
- No se publica en ninguna tienda: se carga como extensión sin empaquetar.
- JavaScript plano, sin dependencias ni paso de build.

## Instalar

1. Arranca la app: `uv run jh serve` en `backend/` (y `pnpm dev` en `frontend/` para la UI).
2. Abre `chrome://extensions` (en Edge, `edge://extensions`).
3. Activa el **Modo de desarrollador** (arriba a la derecha en Chrome; a la izquierda en Edge).
4. Pulsa **Cargar descomprimida** y elige esta carpeta, `extension/`.
5. Fija el botón en la barra: icono del puzle → chincheta junto a «Enviar a Job Hunter».

El id de la extensión es siempre `hnaofhehllbkghfehnehamjbkcmdjmle`: lo fija la clave pública
(`key`) de `manifest.json`, igual en Chrome, Edge y en cualquier equipo. La app solo acepta
peticiones con ese origen. Si cambias la clave, pon el id nuevo en `.env`
(`JH_CAPTURE_EXTENSION_ID`) y reinicia `jh serve`.

La protección real es el **token**: la clave pública está en el repositorio, así que cualquiera
podría montar otra extensión con el mismo id. El origen solo impide que una web cualquiera lo
intente desde tu navegador. No compartas el token; si se filtra, genera otro.

## Conectarla con la app

1. En `backend/`, genera el token:

   ```
   uv run jh capture token
   ```

   Se muestra una sola vez. La app guarda solo su huella en `data/capture_token`. Volver a
   ejecutarlo crea otro y el anterior deja de valer.
2. Abre las opciones de la extensión (clic derecho en su icono → **Opciones**), pega el token y
   guarda. **Probar conexión** comprueba que la app responde y acepta el token, sin crear nada.
3. `uv run jh doctor` muestra «Botón de captura: token creado».

## Usarla

1. Abre una oferta, por ejemplo en LinkedIn con tu sesión iniciada. También vale la vista de
   búsqueda con la oferta abierta a la derecha.
2. Pulsa el botón. El popup dice el resultado:
   - **Nueva**: la oferta entra lista para extraer;
   - **Completada**: era un resumen de una alerta y ya tiene la descripción;
   - **Ya estaba**: la tenías (si estaba cerrada, puedes reabrirla en su ficha);
   - un error, con lo que hay que hacer.

   **Abrir ficha** lleva a la oferta en la UI. El icono queda marcado en esa pestaña: ✓, = o !.
3. Si no encuentra la descripción o la empresa (los portales cambian su HTML), **selecciona con el
   ratón el texto de la oferta**, empresa incluida, y vuelve a pulsar: se envía lo seleccionado.
4. Después, en tu agente, `procesar-ofertas` como con cualquier otra oferta.

## Problemas

| Mensaje | Qué hacer |
|---|---|
| «La app no responde» | Arranca `uv run jh serve`. La extensión solo habla con `http://127.0.0.1:8000`: si sirves la API en otro puerto, cambia `host_permissions` en `manifest.json` y `API_URL` en `core.js`. |
| «Falta el token» o «El token no vale» | `uv run jh capture token` y pégalo en las opciones. |
| «La app no acepta esta extensión» | El id cargado no es el de `JH_CAPTURE_EXTENSION_ID`: revisa `.env` o que `manifest.json` conserve su `key`. |
| «No se puede leer esta página» | Las páginas del navegador y de las tiendas de extensiones no se dejan leer. |
| «No se encontró la descripción» o «la empresa» | Selecciona el texto de la oferta, con la empresa, y vuelve a pulsar. |

## Sobre LinkedIn

Las condiciones de LinkedIn prohíben las extensiones que copian su contenido. Esta solo actúa
cuando la pulsas, oferta a oferta, y equivale a copiar y pegar: no recorre páginas, no busca por
su cuenta ni envía candidaturas. El riesgo es bajo, pero no es cero. Ver ADR-016 en
`docs/DECISIONS.md`.

## Desarrollo

- Los extractores se prueban con Vitest desde el frontend (`frontend/src/extension/`) contra HTML
  **inventado** de `tests/fixtures/`: `pnpm test` en `frontend/`.
- Tras cambiar un fichero, pulsa **Actualizar** en la tarjeta de la extensión en
  `chrome://extensions`.
- Los iconos se generaron con Pillow (el monograma «JH» de la UI).
