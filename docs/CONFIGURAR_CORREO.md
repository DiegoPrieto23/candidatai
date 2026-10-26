# Configurar las alertas de empleo por correo

Guía para que CandidatAI lea las alertas de empleo que te llegan al correo (LinkedIn, InfoJobs,
Indeed, Tecnoempleo) y dé de alta sus ofertas. Puedes conectar **uno o varios buzones** desde la
app, en **Alertas → Añadir buzón**: el asistente tiene una pestaña por proveedor con estos mismos
pasos. Los detalles técnicos están en `FUENTES_OFERTAS.md` §Alertas por correo.

## Qué hace y qué no

- Se conecta por **IMAP en solo lectura** a **una carpeta o etiqueta** de cada buzón para las
  alertas y, si se lo pides, a su bandeja de entrada para las **respuestas** de las empresas (ver
  §Respuestas de las empresas).
- **No** marca nada como leído, **no** mueve ni borra correos y **no** envía nada.
- De cada alerta guarda solo su `Message-ID` (para no procesarla dos veces), nunca el cuerpo. Si
  la misma alerta te llega a dos buzones, cuenta una vez.
- No entra en LinkedIn: sus ofertas llegan como **resumen** (título, empresa, ubicación). La
  descripción completa la traes tú con el botón «Enviar a CandidatAI» de la extensión.
- La contraseña vive solo en el fichero `.env` de tu equipo, que no se sube a git: cuando la
  escribes en el asistente, la app la guarda ahí (una línea `CAI_IMAP_<NOMBRE>_PASSWORD` por
  buzón) y no vuelve a enseñarla ni a dársela a tu agente. Al quitar el buzón, quita su línea.
- **En Docker** la app no puede escribir tu `.env`: el asistente te dice qué línea añadir; después
  recrea el contenedor (`docker compose up -d`).

## Añadir un buzón

1. Pantalla **Alertas** → **Añadir buzón**.
2. Elige la pestaña de tu proveedor y sigue sus pasos (abajo, los mismos con más detalle).
3. Escribe tu dirección y la contraseña de aplicación y pulsa **Probar conexión**: solo inicia
   sesión y abre la carpeta en solo lectura, sin leer ningún correo.
4. **Guardar**. El panel **Buzones** de la misma pantalla enseña cada uno con su última lectura y
   su último error, y deja probarlo, desactivarlo, editarlo o quitarlo.

Repite para cada cuenta en la que te lleguen alertas. Si una falla, las demás se siguen leyendo.

## Gmail

### 1. Activa la verificación en dos pasos

Google la exige para crear contraseñas de aplicación: entra en
[myaccount.google.com](https://myaccount.google.com) → **Seguridad** → **Verificación en dos
pasos** y actívala si no lo está.

### 2. Crea una contraseña de aplicación

1. Ve a [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
2. Ponle un nombre, por ejemplo `CandidatAI`, y pulsa **Crear**.
3. Google enseña 16 letras **una sola vez**: cópialas en el asistente (los espacios no importan).

**Qué permiso das:** Google no ofrece contraseñas limitadas a una etiqueta, así que con ella se
podría leer todo el correo por IMAP. La limitación la pone la app (solo abre la carpeta que le
indicas, con `EXAMINE`). Por eso:

- no la compartas ni la pegues en chats, issues o capturas;
- si dejas de usar la app o sospechas algo, **revócala** desde la misma página: deja de funcionar
  al momento y no afecta a tu contraseña normal.

Si Google dice que la opción no está disponible: o falta la verificación en dos pasos, o tu cuenta
es de una organización (trabajo, universidad) que lo tiene desactivado, o usa la Protección
Avanzada ([ayuda de Google](https://support.google.com/mail/answer/185833)). En ese caso usa una
carpeta de `.eml` (§Carpeta de `.eml`).

### 3. Comprueba que IMAP está disponible

En Gmail: ⚙️ → **Ver todos los ajustes** → **Reenvío y correo POP/IMAP**. Las cuentas personales
tienen IMAP siempre activo; si ves la opción **Habilitar IMAP**, márcala y guarda.

### 4. Crea una etiqueta y un filtro para las alertas

Recomendado: así la app solo ve las alertas y nada más de tu correo.

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
La app las sigue leyendo desde la etiqueta
([ayuda de Google sobre filtros](https://support.google.com/mail/answer/6579)).

### 5. Añádelo en la app

En el asistente, pestaña **Gmail**: tu dirección, las 16 letras y, en **Carpeta o etiqueta de las
alertas**, el nombre exacto de la etiqueta, con mayúsculas, tildes y espacios. Si está anidada
dentro de otra, se escribe con `/`: `Empleo/Alertas empleo`. Pulsa **Probar conexión** y
**Guardar**.

## Outlook y Hotmail

Microsoft ya no deja entrar por IMAP con contraseña en las **cuentas de trabajo o de un centro
educativo** (Exchange Online), y ha anunciado que también lo quitará en las **personales**
(Outlook.com, Hotmail, Live) sin dar fecha
([aviso de Microsoft](https://support.microsoft.com/en-us/office/outlook-and-other-apps-are-unable-to-connect-to-outlook-com-when-using-basic-authentication-f4202ebf-89c6-4a8a-bec3-3d60cf7deaef)).
La app no usa el inicio de sesión de Microsoft (OAuth), así que hay dos caminos que funcionan
(comprobado el 2026-10-23):

- **Reenvía las alertas a otra cuenta (recomendado).** En Outlook.com: **Configuración → Correo →
  Reglas**, una regla para los correos de LinkedIn, InfoJobs… con **Reenviar a** tu Gmail; o
  **Configuración → Correo → Reenvío** para reenviarlo todo
  ([ayuda de Microsoft](https://support.microsoft.com/en-us/office/turn-on-automatic-forwarding-in-outlook-7f2670a1-7fff-4475-8a3c-5822d63b0c8e)).
  Después añade ese Gmail (§Gmail).
- **Exporta las alertas como `.eml`** (§Carpeta de `.eml`). En Outlook en la web, abre una alerta
  → **⋯ → Descargar**.

Si aun así quieres probar IMAP en una cuenta personal, la pestaña **Outlook / Hotmail** tiene
plegado **Probar por IMAP igualmente** (`outlook.office365.com`, puerto 993, con una contraseña de
aplicación y la verificación en dos pasos activada). Puede dejar de funcionar cualquier día.

## Yahoo

1. En la seguridad de tu cuenta de Yahoo, **Conexiones externas → Generar contraseña de
   aplicación** ([ayuda de Yahoo](https://help.yahoo.com/kb/SLN15241.html)).
2. En el asistente, pestaña **Yahoo**: tu dirección completa y esa contraseña. El servidor
   (`imap.mail.yahoo.com`, puerto 993) ya viene puesto
   ([datos IMAP de Yahoo](https://help.yahoo.com/kb/SLN4075.html)).

## iCloud

1. Activa la autenticación de doble factor en tu cuenta de Apple.
2. En [account.apple.com](https://account.apple.com) → **Inicio de sesión y seguridad →
   Contraseñas específicas de app**, genera una
   ([ayuda de Apple](https://support.apple.com/en-us/102654)).
3. En el asistente, pestaña **iCloud**: como usuario, lo que va antes de `@icloud.com` (si no
   conecta, la dirección completa) y esa contraseña. El servidor (`imap.mail.me.com`, puerto 993)
   ya viene puesto ([datos IMAP de iCloud](https://support.apple.com/en-us/102525)).

## Otro proveedor (IMAP)

- Busca en la ayuda de tu proveedor sus datos IMAP: servidor y puerto (casi siempre 993 con SSL;
  el asistente admite también STARTTLS en el 143). Nunca se conecta sin cifrar y siempre
  comprueba el certificado.
- Si tu proveedor da contraseñas de aplicación, usa una.
- Crea una carpeta con una regla que mueva allí las alertas y escribe su nombre en **Carpeta o
  etiqueta de las alertas**.
- **Un servidor en tu equipo o tu red** (una IP privada, `localhost`…): por seguridad, la app no se
  conecta a esas direcciones salvo que marques **Servidor en mi equipo o mi red**.
- **Proton Mail** no da IMAP directo, y su Bridge usa un certificado propio que la app no acepta:
  exporta los correos como `.eml`.

## Carpeta de `.eml`

Sin contraseñas y con cualquier proveedor: exporta los correos de alertas (en Gmail, **⋮ →
Descargar mensaje**; en Outlook en la web, **⋯ → Descargar**) y déjalos en una carpeta.

- En el asistente, pestaña **Carpeta de `.eml`**: ponle un nombre y la app crea
  `data/inbox/<nombre>/`. Puedes tener varias.
- También sigue valiendo dejarlos directamente en `data/inbox/`.
- Se leen `.eml` y `.mbox`, sin moverlos ni borrarlos; los ya procesados se reconocen por su
  `Message-ID`.

## La cuenta de `.env` (como antes)

Si ya tenías el correo configurado en `.env`, no tienes que hacer nada: aparece sola en el panel
**Buzones** como «Principal» (con la etiqueta «de .env») y lee también las respuestas de las
empresas. Su servidor, usuario y carpetas se siguen cambiando en `.env`; desde la app puedes
desactivarla, cambiarle el nombre o decidir si lee respuestas.

Para configurarla a mano, el fichero `.env` va en la **raíz del proyecto** (junto a `README.md`):

```
CAI_IMAP_HOST=imap.gmail.com
CAI_IMAP_PORT=993
CAI_IMAP_USER=tu.correo@gmail.com
CAI_IMAP_PASSWORD=abcdefghijklmnop
CAI_IMAP_FOLDER="Alertas empleo"
```

Reinicia la app para que lea el `.env` nuevo.

## Comprueba la conexión

**Probar** en el panel **Buzones**, o desde `backend/`: `uv run cai mail-sources test ID` (uno) o
`uv run cai doctor` (todos; solo hacen login y abren la carpeta en solo lectura). Si falla:

| Mensaje | Qué revisar |
|---|---|
| «rechazó el usuario o la contraseña» | La contraseña de aplicación (no tu contraseña normal) y el usuario (la dirección completa; en iCloud, lo que va antes de la @) |
| «caracteres que IMAP no admite» | La contraseña o el usuario llevan tildes o ñ: las contraseñas de aplicación no, genera una |
| «rechazó abrir la carpeta…» | El nombre de la carpeta o etiqueta, letra por letra |
| «No se pudo conectar con…» | El servidor y el puerto, tu conexión, o un cortafuegos o antivirus que bloquee el puerto |
| «Falta la contraseña» | Escríbela en **Editar** (o, en Docker, añade la línea que dice a tu `.env`) |
| «dirección privada o local» | Si es tu propio servidor, marca **Servidor en mi equipo o mi red** |
| «IMAP a medias» (`cai doctor`) | En la cuenta de `.env`, falta `CAI_IMAP_HOST`, `CAI_IMAP_USER` o `CAI_IMAP_PASSWORD` |

## Primera lectura

- En la UI, pantalla **Alertas** → **Revisar correo ahora**, o desde `backend/`:
  `uv run cai alerts poll`.
- Después, el worker la repite solo cada `email_alerts.poll_minutes` minutos (60 por defecto, en
  `config/policies.yaml`). Lee los correos de los últimos `summary_expire_days` días (21), buzón
  a buzón; si en una pasada no da tiempo a todos (5 minutos), los que faltan se leen en la
  siguiente.

## Qué hacer con lo que entra

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

En los buzones que lo tengan marcado («Leer aquí también las respuestas de las empresas»; la
cuenta de `.env`, siempre), la app lee también las **respuestas de las empresas** a tus
candidaturas (entrevista, prueba, oferta, rechazo) y las deja como propuesta en la ficha de la
oferta. Tú decides: nada cambia de etapa hasta que pulsas «Aceptar».

- **Carpeta:** la bandeja de entrada (`INBOX`). En la cuenta de `.env` se cambia con
  `CAI_IMAP_REPLIES_FOLDER`: si prefieres limitarla, crea una etiqueta (p. ej. «Procesos») con un
  filtro de Gmail y pon su nombre: `CAI_IMAP_REPLIES_FOLDER="Procesos"`.
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
- **Clasificarlos:** el skill `review-replies` de tu agente propone para cada correo el evento
  (entrevista con su fecha, prueba, oferta, rechazo, respuesta o nada) y tú lo aceptas, cambias o
  ignoras en la pantalla «Respuestas» o en el aviso de la ficha de la oferta. Si hay correos sin
  clasificar, Inicio y «Respuestas» muestran el botón «Revisar respuestas», que abre tu agente con
  la orden. El texto de los correos es contenido no confiable: si trae instrucciones para una IA, se
  marca y no se obedece.
- **Contestar:** la app no envía correo. Los seguimientos (como mucho 2 por candidatura) y los
  agradecimientos tras una entrevista los redacta tu agente con `draft-follow-up` como
  borradores en la ficha de la oferta; los copias, los mandas desde tu correo y pulsas «Ya lo he
  enviado».
