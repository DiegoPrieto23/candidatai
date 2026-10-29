# Enviar a CandidatAI

Extensión mínima para navegadores Chromium (Chrome, Edge, Brave) que envía la oferta que estás
viendo a tu CandidatAI local con un clic. Detalle y límites en `docs/FUENTES_OFERTAS.md`
§Botón «Enviar a CandidatAI».

- **Solo actúa cuando pulsas su botón**, en la pestaña actual. No se queda cargada en ninguna web,
  no lee cookies, no recorre páginas ni lee nada en segundo plano.
- Permisos: `activeTab`, `scripting` y `storage`. Solo puede hablar con `http://127.0.0.1:8000`.
- Lee la página que ya tienes delante: el texto que hayas seleccionado o, si no hay selección, la
  oferta (extractores para LinkedIn, InfoJobs, Indeed y Tecnoempleo; JSON-LD `JobPosting`; `main`).
- Si la oferta ya estaba como resumen de una alerta, la completa; si ya estaba completa, te lo
  dice; si no, la da de alta.
- No se publica en ninguna tienda: se carga como extensión sin empaquetar.
- JavaScript plano, sin dependencias ni paso de build.

## Instalar y conectar

Lo más fácil es dejar que te guíe la app: abre CandidatAI en Chrome, Edge o Brave y ve a **Dónde
buscar → Botón del navegador**. La página detecta la extensión sola y avanza a medida que la cargas:

1. **«Abrir la carpeta de la extensión»** te abre esta carpeta, `extension/`, la que trae la app.
2. Abre `chrome://extensions` (en Edge, `edge://extensions`) y activa el **Modo de desarrollador**
   (arriba a la derecha en Chrome; a la izquierda en Edge).
3. Pulsa **Cargar descomprimida** y elige la carpeta. Si ya la tenías cargada, pulsa el botón de
   recargar (⟳) de su tarjeta en vez de cargarla otra vez: la página avisa si tienes una versión
   antigua.
4. De vuelta en la app, pulsa **Conectar**. La app crea una clave y se la pasa a la extensión, que
   la comprueba antes de guardarla. No hay que copiar nada.
5. Fija el botón en la barra: icono del puzle → chincheta junto a «Enviar a CandidatAI».

Si pulsas el botón sin haberla conectado, el popup ofrece **Conectar con CandidatAI**, que abre esa
página de la app.

No se publica en ninguna tienda: se carga como extensión sin empaquetar, así que no se actualiza
sola. Al actualizar CandidatAI, pulsa ⟳ en su tarjeta.

### Cómo se conecta

La extensión deja que le escriban las páginas de `http://127.0.0.1` y `http://localhost`
(`externally_connectable`) y vuelve a comprobar el origen. La app le pregunta su versión y si está
conectada, y al pulsar **Conectar** le pasa un token nuevo (`POST /capture/pair`, que solo acepta
la UI). La extensión lo prueba contra `POST /capture` y solo lo guarda si la app lo acepta: otra
página local no puede desconectarla con uno falso. Conectar otra vez invalida el anterior. La app
guarda solo la huella del token en `data/capture_token`.

Sin la UI, también vale a mano: `uv run cai capture token` en `backend/` lo genera y lo muestra una
vez; pégalo en las opciones de la extensión (clic derecho en su icono → **Opciones → Avanzado**).
`uv run cai doctor` muestra «Botón de captura: token creado».

El id de la extensión es siempre `hnaofhehllbkghfehnehamjbkcmdjmle`: lo fija la clave pública
(`key`) de `manifest.json`, igual en Chrome, Edge y en cualquier equipo. La app solo acepta
peticiones con ese origen. Si cambias la clave, pon el id nuevo en `.env`
(`CAI_CAPTURE_EXTENSION_ID`) y reinicia CandidatAI.

La protección real es el **token**: la clave pública está en el repositorio, así que cualquiera
podría montar otra extensión con el mismo id. El origen solo impide que una web cualquiera lo
intente desde tu navegador.

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
4. Después, en tu agente, `process-jobs` como con cualquier otra oferta.

## Problemas

| Mensaje | Qué hacer |
|---|---|
| «CandidatAI no responde» | Abre CandidatAI. La extensión solo habla con `http://127.0.0.1:8000`: si sirves la API en otro puerto, cambia `host_permissions` en `manifest.json` y `API_URL` en `core.js`. |
| «Falta conectar la extensión» o «La conexión ya no vale» | **Conectar con CandidatAI** en el popup, y en la app, **Conectar**. |
| La app dice que no encuentra la extensión | Recárgala (⟳) en `chrome://extensions`: las versiones anteriores a la 0.2.0 no saben hablar con la app. |
| «La app no acepta esta extensión» | El id cargado no es el de `CAI_CAPTURE_EXTENSION_ID`: revisa `.env` o que `manifest.json` conserve su `key`. |
| «No se puede leer esta página» | Las páginas del navegador y de las tiendas de extensiones no se dejan leer. |
| «No se encontró la descripción» o «la empresa» | Selecciona el texto de la oferta, con la empresa, y vuelve a pulsar. En LinkedIn, la sección «Acerca del empleo» se carga al llegar a ella: baja hasta verla (no hace falta pulsar «… más») y vuelve a pulsar. |

## Sobre LinkedIn

Las condiciones de LinkedIn prohíben las extensiones que copian su contenido. Esta solo actúa
cuando la pulsas, oferta a oferta, y equivale a copiar y pegar: no recorre páginas, no busca por
su cuenta ni envía candidaturas. El riesgo es bajo, pero no es cero.

## Desarrollo

- Los extractores se prueban con Vitest desde el frontend (`frontend/src/extension/`) contra HTML
  **inventado** de `tests/fixtures/`: `pnpm test` en `frontend/`.
- Tras cambiar un fichero, pulsa **Actualizar** en la tarjeta de la extensión en
  `chrome://extensions`.
- Los iconos salen del logo (`docs/brand/mark.svg`) con `scripts/build_icons.py`.
