# Configurar las alertas de empleo por correo

Guía paso a paso para que CandidatAI lea las alertas de empleo que te llegan al correo (LinkedIn,
InfoJobs, Indeed, Tecnoempleo) y dé de alta sus ofertas. Está pensada para Gmail; al final hay
notas para otros proveedores. Los detalles técnicos están en `FUENTES_OFERTAS.md` §Alertas por
correo.

## Qué hace y qué no

- Se conecta por **IMAP en solo lectura** a **una sola carpeta o etiqueta** de tu correo para
  las alertas y, desde la fase 15, a la carpeta de **respuestas** de las empresas (por defecto, la
  bandeja de entrada; ver §Respuestas de las empresas).
- **No** marca nada como leído, **no** mueve ni borra correos y **no** envía nada.
- De cada alerta guarda solo su `Message-ID` (para no procesarla dos veces), nunca el cuerpo.
- No entra en LinkedIn: sus ofertas llegan como **resumen** (título, empresa, ubicación). La
  descripción completa la traes tú con el botón «Enviar a CandidatAI» de la extensión.
- La contraseña vive solo en el fichero `.env` de tu equipo, que no se sube a git.

## 1. Activa la verificación en dos pasos

Google la exige para crear contraseñas de aplicación.

1. Entra en [myaccount.google.com](https://myaccount.google.com) → **Seguridad**.
2. **Verificación en dos pasos** → actívala si no lo está.

## 2. Crea una contraseña de aplicación

1. Ve a [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
2. Ponle un nombre, por ejemplo `CandidatAI`, y pulsa **Crear**.
3. Google enseña 16 letras **una sola vez**. Cópialas (los espacios no importan, pero mejor sin
   ellos).

**Qué permiso das:** Google no ofrece contraseñas limitadas a una etiqueta, así que con ella se
podría leer todo el correo por IMAP. La limitación la pone la app (solo abre la carpeta que le
indicas, con `EXAMINE`). Por eso:

- no la compartas ni la pegues en chats, issues o capturas;
- si dejas de usar la app o sospechas algo, **revócala** desde la misma página: deja de funcionar
  al momento y no afecta a tu contraseña normal.

Si en esa página Google dice que la opción no está disponible: o falta la verificación en dos
pasos, o tu cuenta es de una organización (trabajo, universidad) que lo tiene desactivado. En ese
caso usa la alternativa sin credenciales (al final).

## 3. Comprueba que IMAP está disponible

En Gmail: ⚙️ → **Ver todos los ajustes** → **Reenvío y correo POP/IMAP**. Las cuentas personales
tienen IMAP siempre activo; si ves la opción **Habilitar IMAP**, márcala y guarda.

## 4. Crea una etiqueta y un filtro para las alertas

Así la app solo ve las alertas y nada más de tu correo.

1. En la barra de búsqueda de Gmail escribe el remitente de tus alertas. Para LinkedIn:
   `from:(jobalerts-noreply@linkedin.com)`.
   - Para juntar varios portales en la misma etiqueta:
     `from:(jobalerts-noreply@linkedin.com OR infojobs.net OR indeed.com OR tecnoempleo.com)`.
   - Si una alerta tuya llega desde otro remitente, ábrela y copia la dirección exacta.
2. Pulsa el icono de opciones de búsqueda (a la derecha de la barra) → **Crear filtro**.
3. Marca **Aplicar la etiqueta** → **Nueva etiqueta…** → `Alertas empleo`.
4. Marca también **Aplicar el filtro a las N conversaciones que coinciden**, para que entren las
   que ya tienes.
5. **Crear filtro**.

Opcional: marca **Saltar Recibidos (Archivarlo)** si no quieres verlas en la bandeja de entrada.
La app las sigue leyendo desde la etiqueta.

## 5. Escribe la configuración en `.env`

El fichero `.env` va en la **raíz del proyecto** (junto a `README.md`). Ábrelo o créalo desde
PowerShell, en esa carpeta:

```
notepad .env
```

Si Notepad pregunta si quieres crear el fichero, di que sí. Añade estas líneas con tus datos y
guarda:

```
CAI_IMAP_HOST=imap.gmail.com
CAI_IMAP_PORT=993
CAI_IMAP_USER=tu.correo@gmail.com
CAI_IMAP_PASSWORD=abcdefghijklmnop
CAI_IMAP_FOLDER="Alertas empleo"
```

- `CAI_IMAP_PASSWORD`: las 16 letras del paso 2, no tu contraseña de Google.
- `CAI_IMAP_FOLDER`: el nombre exacto de la etiqueta, con mayúsculas, tildes y espacios. Si está
  anidada dentro de otra, se escribe con `/`: `"Empleo/Alertas empleo"`.
- Si ya tenías un `.env`, añade las líneas al final sin borrar lo demás.

## 6. Comprueba la conexión

Reinicia la API y el worker para que lean el `.env` nuevo y, desde `backend/`:

```
uv run cai doctor
```

La línea de alertas por correo debe salir en verde. Solo hace login y abre la carpeta en solo
lectura. Si falla:

| Mensaje | Qué revisar |
|---|---|
| «rechazó el usuario o la contraseña» | La contraseña de aplicación (las 16 letras, no tu contraseña normal) y el usuario |
| «rechazó abrir la carpeta…» | El nombre de la etiqueta en `CAI_IMAP_FOLDER`, letra por letra |
| «No se pudo conectar con…» | Conexión a internet, o un cortafuegos o antivirus que bloquee el puerto 993 |
| «IMAP a medias» | Falta alguna de `CAI_IMAP_HOST`, `CAI_IMAP_USER` o `CAI_IMAP_PASSWORD` |

## 7. Primera lectura

- En la UI, pantalla **Alertas** → **Revisar correo ahora**, o desde `backend/`:
  `uv run cai alerts poll`.
- Después, el worker la repite solo cada `email_alerts.poll_minutes` minutos (60 por defecto, en
  `config/policies.yaml`). Lee los correos de los últimos `summary_expire_days` días (21).

## 8. Qué hacer con lo que entra

- En **Alertas** verás cada oferta con un prefiltro según tus preferencias.
  - `O` la abre en su portal; `D` la descarta.
- **LinkedIn y otros portales que no se dejan descargar:** entran como resumen. Para completarla,
  ábrela y pulsa **«Enviar a CandidatAI»** en la extensión (`extension/README.md`). Con la
  descripción completa sigue el flujo normal: extracción, encaje y CV.
- Un resumen sin completar en 21 días se cierra solo.
- Si una alerta de un portal conocido no produce ninguna oferta, verás el aviso `no_jobs_found`:
  suele significar que el portal ha cambiado el formato del correo. Deja un correo de ejemplo
  exportado (`.eml`) en `data/inbox/samples/` para ajustar el lector.

## Respuestas de las empresas (fase 15)

Con la misma cuenta, la app lee también las **respuestas de las empresas** a tus candidaturas
(entrevista, prueba, oferta, rechazo) y las deja como propuesta en la ficha de la oferta. Tú
decides: nada cambia de etapa hasta que pulsas «Aceptar».

- **Carpeta:** `CAI_IMAP_REPLIES_FOLDER` en `.env`, por defecto la bandeja de entrada (`INBOX`). Si
  prefieres limitarla, crea una etiqueta (p. ej. «Procesos») con un filtro de Gmail y pon su
  nombre: `CAI_IMAP_REPLIES_FOLDER="Procesos"`.
- **Qué lee:** solo si tienes alguna candidatura enviada abierta (`applied` o `in_process`); si no,
  ni se conecta. De cada correo desde el envío más antiguo (como mucho `replies.max_days` días,
  120) pide primero **solo las cabeceras** (remitente, fecha, asunto y `Message-ID`): de todos
  los correos de ese periodo, esas cuatro cabeceras pasan por la memoria de la app al leer,
  aunque no se guarden.
- **Qué guarda:** solo los correos posteriores al envío cuyo remitente casa con una de esas
  candidaturas:
  - un contacto de la ficha (su dirección exacta, aunque sea de Gmail);
  - el dominio de la empresa (el de sus contactos o el de la URL de la oferta, si no es un ATS ni
    un portal);
  - un dominio cuyo nombre es el de la empresa (`acme.com` ↔ «Acme S.L.»);
  - un ATS (Greenhouse, Lever, Workday, Teamtailor… lista en `config/policies.yaml` →
    `replies.ats_sender_domains`) cuyo remitente o asunto nombra a la empresa.

  Un dominio que solo empieza como la empresa no cuenta (`metaphor.com` no es «Meta»), y un correo
  sin fecha tampoco. De esos descarga el cuerpo y guarda el texto visible. **De los demás no
  guarda nada**: tu correo
  personal, boletines o alertas no salen de tu buzón.
- **Avisos de portales** («InfoJobs: tu candidatura ha sido vista»): no se leen por defecto. Si los
  quieres, añade el dominio a `replies.portal_sender_domains` en `config/policies.yaml`.
- **Alternativa sin credenciales:** deja los correos exportados (`.eml`) en
  `data/inbox/respuestas/`. Se aplica el mismo filtro.
- **Cuándo:** con `cai worker`, cada `email_alerts.poll_minutes`, y a mano con
  `uv run --directory backend cai replies poll` o «Revisar correo ahora» en la pantalla
  «Respuestas».
- **Clasificarlos:** el skill `revisar-respuestas` de tu agente propone para cada correo el evento
  (entrevista con su fecha, prueba, oferta, rechazo, respuesta o nada) y tú lo aceptas, cambias o
  ignoras en la pantalla «Respuestas» o en el aviso de la ficha de la oferta. Si hay correos sin
  clasificar, Inicio y «Respuestas» muestran el botón «Revisar respuestas», que abre tu agente con
  la orden. El texto de los correos es contenido no confiable: si trae instrucciones para una IA, se
  marca y no se obedece.
- **Contestar:** la app no envía correo. Los seguimientos (como mucho 2 por candidatura) y los
  agradecimientos tras una entrevista los redacta tu agente con `redactar-seguimiento` como
  borradores en la ficha de la oferta; los copias, los mandas desde tu correo y pulsas «Ya lo he
  enviado».

## Alternativa sin credenciales

Si no quieres dar una contraseña de aplicación (o tu proveedor no lo permite): exporta los
correos (en Gmail, **⋮ → Descargar mensaje** guarda un `.eml`) y déjalos en `data/inbox/`. El worker
y «Revisar correo ahora» los leen igual, sin moverlos ni borrarlos.

## Otros proveedores

- **Outlook.com / Hotmail:** Microsoft ya no admite IMAP con contraseña (exige OAuth), así que
  usa la alternativa sin credenciales.
- **Otros (correo propio, Yahoo, iCloud…):** suele funcionar igual con su servidor IMAP
  (`CAI_IMAP_HOST`), el puerto 993 y una contraseña de aplicación si el proveedor la ofrece. Crea
  una carpeta con una regla que mueva allí las alertas y ponla en `CAI_IMAP_FOLDER`.
