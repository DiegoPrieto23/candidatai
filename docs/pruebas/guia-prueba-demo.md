# Guía para probar CandidatAI con la demo

Un recorrido por todas las funciones de la app con los **datos de la demo**: qué probar, dónde
tocar y qué deberías ver. No toca tus datos de `data/`. Marca cada casilla al probarla y apunta al
final lo que no cuadre.

Hay dos demos con la misma búsqueda: **en español** (Lucía, en Galicia) y **en inglés** (Aoife, en
Dublín). Esta guía sigue la española; con la inglesa todo es igual, con otros nombres.

> Las referencias como «ficha #1» son el número de la oferta: ábrela en
> `http://127.0.0.1:8000/jobs/1`. La demo es determinista: los números no cambian al recrearla.

> Además del embudo, la demo trae hecho lo que dejarían Lucía y su agente (desde la fase 26.5):
> la ficha #1 (Brétema Analytics) con valoración, carta, respuestas de screening y dosier; la #2
> (Lumieira Retail) con un mensaje de LinkedIn y un dosier con bandera roja; tres correos en
> «Respuestas»; el plan de una entrevista y el repaso de dos; la oferta recibida de la #60; un
> seguimiento; dos huecos en «Skills»; un encargo; el contexto, una muestra de estilo y una tabla
> de salarios. Si tu demo es anterior, recréala con `--force`.

---

## 0. Preparar

- [ ] **Compilar la UI** (si clonaste el repositorio; desde la raíz): `cd frontend; pnpm install;
  pnpm build; cd ..`. Repítelo tras cada `git checkout` o `git pull`: `cai start` sirve la UI
  compilada y con una vieja faltan pantallas y botones.

- [ ] **Crear la demo** (desde `backend/`, en PowerShell):

  ```powershell
  uv run cai demo seed --force                          # española, en data-demo/
  uv run cai demo seed --lang en --dir data-demo-en --force   # inglesa (opcional)
  ```

  Debe decir «60 ofertas», un reparto por etapas y «CVs verificados: 2».

- [ ] **Arrancar la app con la demo** en una ventana propia:

  ```powershell
  $env:CAI_DATA_DIR = "data-demo"; uv run cai start
  ```

  Se abre el navegador en `http://127.0.0.1:8000`. Arriba sale la franja amarilla **«Modo demo:
  datos ficticios»** en todas las páginas.

- [ ] **Con agente (opcional, sección 15):** los botones «en tu agente» ya lo abren sobre la demo.
  Si lo abres tú, arráncalo con `CAI_DATA_DIR=data-demo` para que use la demo y no tus datos.

> Si algo falla al arrancar, mira `data-demo/logs/start-*.log`.

---

## 1. Navegación, idioma y tema

| Probar | Dónde | Qué debe pasar |
|---|---|---|
| [ ] Barra lateral | Izquierda | Grupos **Búsqueda**, **Procesos**, **Análisis** y **Configurar**. «Por revisar» lleva un **8** en verde |
| [ ] Plegar la barra | Abajo: «Plegar el menú» | Quedan solo los iconos; al pasar el ratón, un tooltip con el nombre. Se recuerda al recargar |
| [ ] Idioma | Abajo: botón del globo, «Español» con su bandera | Menú con 🇪🇸 Español y 🇬🇧 English (✓ en el actual). Al elegir English, **toda la interfaz** pasa a inglés al momento; recarga: se mantiene |
| [ ] Tema | Abajo: «Tema: …» | Cicla sistema → claro → oscuro. Todo legible en oscuro |
| [ ] Móvil | Estrecha la ventana (< 1024 px) | La barra desaparece; arriba sale ☰. Al pulsarlo se abre un cajón con el menú, el idioma y el tema; al navegar se cierra |
| [ ] Página inexistente | `http://127.0.0.1:8000/no-existe` | «Esta página no existe» con botón a Inicio |

> En inglés, los títulos de las ofertas y los nombres de la demo española siguen en español: son
> datos, no textos de la interfaz. Algunos mensajes del servidor (motivos de los filtros, notas
> del score) también siguen en español: es el límite conocido de la fase 23.6.

---

## 2. Inicio

| Probar | Qué debe pasar |
|---|---|
| [ ] Resumen del día | Titular «Tienes 8 ofertas por revisar, 2 CVs listos para enviar y 6 seguimientos pendientes». Cada parte es un enlace a su lista |
| [ ] «Para tu agente» | «3 por extraer y 3 aprobadas sin CV» |
| [ ] Botones | **Nueva oferta** (va al alta), **Buscar ofertas**, **Procesar ofertas**, **Evaluar encaje**. Los del agente abren tu agente en una terminal (sección 15); su flecha ofrece «En segundo plano» y «Dejar para mi próxima sesión» |
| [ ] Sin cabecera arriba | En escritorio, Inicio no tiene la fila de arriba con «Nueva oferta» (en las demás páginas sí) |
| [ ] Recorrido | 7 casillas con lo que hay en cada etapa; las que te tocan, en verde. Cada una lleva a su lista |
| [ ] Paneles | «Mejor encaje por revisar», «Listas para enviar» (las 2 con CV), «Próximos 7 días» (entrevistas y pruebas) y «Sin respuesta» |
| [ ] Avisos de arriba | «Hay 3 ofertas por extraer» con «Procesar ahora», y «6 candidaturas llevan 10 días o más sin respuesta» con enlace a Procesos |

---

## 3. Bandeja

`Bandeja` en la barra lateral.

- [ ] **Recuentos por etapa** en la cabecera (Todas 60, Por completar 0, Por extraer 3…). Al pulsar
  uno, la lista se filtra y la URL cambia (`?stage=…`).
- [ ] **Buscar** «Data» en el buscador: filtra por título o empresa; el texto de arriba dice
  «… que coinciden con «Data»». Con algo que no exista: «Nada por aquí» y «Quitar filtros».
- [ ] **Ordenar** pulsando las cabeceras **Salario**, **Encaje** y **Alta** (la flecha cambia de
  sentido al pulsar otra vez). En móvil, el selector «Ordenar».
- [ ] **Paginación** abajo («1-50 de 60», «Anteriores», «Siguientes»).
- [ ] Insignias en las filas: **«Conoces a N»** (red de LinkedIn) y el ⚠️ de la ficha #3.

---

## 4. Nueva oferta

`+ Nueva oferta` (arriba en cualquier página salvo Inicio, o el botón de Inicio).

- [ ] **Pegar texto**: pestaña «Pegar texto», copia el contenido de `demo/jobs/01-data-engineer.txt`,
  título «Data Engineer», empresa «Brétema Analytics». Al darla de alta debe abrir la ficha con
  el aviso **«parece un duplicado de la oferta 1, así que queda cerrada»** (la #1 es la misma).
- [ ] **Pegar texto nuevo**: inventa una oferta (título y empresa que no existan). Debe quedar
  «Por extraer» con el aviso «Tu agente la extraerá con el skill process-jobs».
- [ ] **Por URL**: una URL pública real de Greenhouse o Lever (necesita internet). Con LinkedIn te
  recuerda que pegues el texto.

---

## 5. Por revisar (triaje)

`Por revisar` en la barra lateral. 8 ofertas, de más a menos encaje.

| Probar | Qué debe pasar |
|---|---|
| [ ] Lista y detalle | A la izquierda la cola; a la derecha, la seleccionada con su **score** grande, datos (modalidad, nivel, años, ciudad, salario), **Desglose** del score, skills **obligatorias** y **deseables** (✓ las que tienes, punteadas las que no) y «Valoración del agente» (sin valorar) |
| [ ] Teclado | `J`/`K` (o flechas) se mueven, `O` abre la ficha, `A` aprueba, `D` descarta |
| [ ] Aprobar | `A`: desaparece de la cola, aviso «Aprobada …» y la siguiente queda seleccionada |
| [ ] Descartar | `D`: diálogo con 7 motivos (teclas 1-7). «Otro motivo» exige nota. Al confirmar, aviso «Descartada · motivo» con **Deshacer**: al pulsarlo vuelve a la cola |
| [ ] Oferta con riesgo | Analytics Engineer de **Lonxa Retail Tech** (ficha #3): ⚠️ en la lista; su texto lleva una instrucción para IAs |
| [ ] Red | En esa misma oferta: «Conoces a 1 persona en Lonxa Retail Tech: Breixo Fariña Souto (Head of Data)» |
| [ ] Por debajo del umbral | Las de score bajo salen atenuadas |

---

## 6. Ficha de una oferta

Abre la **ficha #1** (Data Engineer · Brétema Analytics, «CV listo»).

### Arriba y a la derecha
- [ ] Título, empresa, etapa «CV listo» y «Ver original».
- [ ] **Encaje** (derecha): score con su desglose.
- [ ] **Tu red**: «Conoces a 3 personas en Brétema Analytics», con «Añadir al proceso» en cada una.
  Añade una como «Referencia»: pasa a «Ya es contacto del proceso» y aparece en **Proceso →
  Contactos**.
- [ ] **Historial**: los eventos, lo último arriba; si son muchos, «Ver N eventos más».
- [ ] **Añadir nota**: escribe algo y «Guardar nota»: aparece en el historial.

### Bloques de la izquierda
- [ ] **Extracción**: seniority, modalidad, experiencia, contrato, salario, idiomas, skills,
  responsabilidades y «Extraída el …».
- [ ] **Proceso**: «Envío» (aún sin enviar), **Hitos** → «Añadir» un «Plazo» o «Otro hito» (las
  entrevistas y pruebas solo se anotan tras enviar). Descarga su `.ics` con el icono.
- [ ] **Valoración del agente**: «Encaje fuerte», con su riesgo (dbt) y su pregunta.
- [ ] **Borradores**: vacío; «Redactar mensaje» abre tu agente (sección 15). En la ficha #2 hay un
  mensaje de LinkedIn para el recruiter, con «Copiar».
- [ ] **Empresa**: el dosier de Brétema Analytics con sus fuentes numeradas; «Investigar empresa»
  lo rehace con tu agente. En la #2, «Banderas rojas» con un ERE, su fecha y su fuente.
- [ ] **Paquete de candidatura**: el CV elegido para enviar y **Respuestas de screening**: tres, y
  la de la expectativa salarial en ámbar «Falta un dato tuyo». Escríbela y «Copiar». «Añadir
  pregunta» añade otra.
- [ ] **Candidatura asistida**: «Preparar candidatura» abriría `empleo.example.com` en el navegador
  de CandidatAI. Ese dominio no existe: **no lo pruebes con la demo** (sí con una oferta real).
- [ ] **CV**:
  - «Verificado: nada inventado ni exagerado»;
  - **Plantilla**: elige otra, cambia **Foto** y **Color**, oculta una sección y «Renderizar»
    (tarda unos segundos; con LibreOffice sale también el DOCX);
  - en **Renders**: «Ver PDF», marca «Comparar» en dos y se ven **lado a lado**;
  - «Usar este para enviar» en otro render: pasa a «Para enviar» y el Paquete lo refleja.
- [ ] **Carta de presentación**: verificada, con las indicaciones de Lucía (la migración a Snowflake,
  producto propio) y su PDF. Cambia las indicaciones y guarda; la carta nueva la redacta tu agente.
- [ ] **Texto original**: se despliega; es el texto tal cual se guardó.

### Otras fichas
- [ ] **Ficha #3** (la del riesgo): bloque amarillo **«Posible contenido dirigido a una IA»** con
  la frase sospechosa.
- [ ] **Una cerrada** (filtra la Bandeja por «Cerrada»): botón **Reabrir**; vuelve a la etapa en
  la que estaba.
- [ ] **Una enviada** (etapa «Enviada»): bloque **«¿Qué ha pasado con esta candidatura?»** con
  botones (Me han respondido, Tengo entrevista, Me han rechazado…). Pulsa «Tengo entrevista»: pide
  fecha y hora, crea el hito y la oferta pasa a «En proceso».
- [ ] **Ficha #60** («En proceso», con oferta): bloque **Oferta recibida** con los datos ya anotados
  (fijo, variable, modalidad, beneficios, incorporación y fecha de respuesta). Cambia uno y guarda:
  el historial dice qué campo cambió, sin el valor. Sale «Preparar negociación». En **Proceso**, la
  entrevista ya hecha tiene su «Repaso».

---

## 7. Procesos

`Procesos` en la barra lateral.

| Probar | Qué debe pasar |
|---|---|
| [ ] Tablero | 5 columnas (Aprobada, CV listo, Enviada, En proceso, Cerrada) con tarjetas: hito próximo 📅, «Seguimiento · N días», motivo de cierre |
| [ ] Actualizar estado | «Actualizar estado» en una tarjeta de «Enviada»: diálogo «Mover proceso» con los eventos posibles. Elige «Enviada por tu cuenta» o «Rechazada», fecha y nota → «Registrar»: cambia de columna |
| [ ] Arrastrar | Arrastra una tarjeta de «Enviada» a «En proceso»: abre el mismo diálogo. A «CV listo»: se niega y explica por qué |
| [ ] Seguimientos | Arriba a la derecha «6 seguimientos pendientes» y «Redactar borradores» (agente) |
| [ ] Ofertas recibidas | **Ofertas recibidas** con la de la ficha #60 y la comparación (fijo y total anual, frente a tu mínimo y al rango publicado) |
| [ ] Próximos 7 días | Entrevistas y pruebas de la semana. La más próxima tiene «Plan de preparación» (bloques de hoy al día de la entrevista) |
| [ ] Calendario | «Llevar los hitos a tu calendario»: «Descargar .ics» y «Copiar dirección» |

---

## 8. Respuestas

`Respuestas`. La demo trae tres correos de empresas de candidaturas enviadas (en
`data-demo/inbox/respuestas/`), cada uno con su oferta como única candidata.

- [ ] **Invitación a entrevista**, con propuesta: «Entrevista programada» y el hito con fecha y
  hora. «Aceptar» → la oferta pasa a «En proceso» con el hito.
- [ ] **Descarte**, con propuesta «Rechazada». «Cambiar» antes de aceptar, o «Ignorar».
- [ ] **Acuse de recibo**, «Sin clasificar», con el aviso de **texto oculto** dirigido a una
  IA. «Revisar respuestas» (agente) lo clasifica como «Nada que registrar», sin hacer caso del
  texto oculto.
- [ ] Filtros **Pendientes / Aceptadas / Ignoradas / Todas** y «Revisar correo ahora» (sin IMAP
  dice que no hay nada nuevo).
- Más casos de clasificación: `docs/pruebas/fase-15-prueba-manual.txt`.

## 9. Alertas

`Alertas`. En la demo está vacía («Sin alertas pendientes»): las alertas llegan por correo (IMAP o
`.eml` en `data-demo/inbox/`). Para probarla, `docs/pruebas/fase-09b-prueba-manual.txt`.

---

## 10. Embudo

`Embudo` en la barra lateral.

- [ ] **Cifras de arriba**: Encontradas 60, Enviadas, Tasa de respuesta, Primera respuesta.
- [ ] **Embudo** por pasos con su conversión, **Por semana** (8 semanas), **Por fuente**, **Por
  tipo de puesto**, **Motivos de descarte**.
- [ ] **Periodo**: Todo / 30 días / 90 días / 12 meses y «Desde» con una fecha: todo se recalcula.
- [ ] **¿Acierta el score?**: pestañas Score, Veredicto, Fuente… con «pocos datos» (la demo tiene
  menos de 20 enviadas) y «Revisar mi búsqueda» (agente).

## 11. Skills

`Skills`: lo que piden tus ofertas y tu perfil no cubre.

- [ ] Filtros **Periodo**, **Tipo** (obligatorias / deseables) y **Marca**; ordenar por «Ofertas» o
  «Peso».
- [ ] **«Es lo mismo que…»** en una skill: elige una del perfil y «Son lo mismo» → aviso de que
  cuenta como esa y el score se recalcula. (Lo guarda en `config/skill_aliases.yaml`: deshazlo
  después si no lo quieres.)
- [ ] **La tengo / No la tengo**: Looker y Databricks ya salen «No la tengo» (filtro **Marca**).
  Marca otras; arriba aparece «Añadir al perfil las que tengo (N)» y «Plan de formación» se
  resalta.

---

## 12. Fuentes

`Fuentes` en la barra lateral, con dos pestañas.

- [ ] **Empresas objetivo**: «Brisa Atlántica Software» (Greenhouse) y «Meiga Fintech» (Lever),
  **pausadas** (sus tableros son inventados). «Probar» fallará por eso; «Reactivar»/«Pausar» sí.
- [ ] **Añadir empresa**: con una real (p. ej. Greenhouse y su slug) y «Probar»: lista lo que
  encontraría y cuántas pasan tus filtros (necesita internet). No hace falta guardarla.
- [ ] **Plataformas**: trae cuatro (InfoJobs, Tecnoempleo, Indeed y LinkedIn; en la demo inglesa,
  Indeed, IrishJobs, Jobs.ie y LinkedIn), cada una con su acceso, su prioridad y búsquedas de
  ejemplo. LinkedIn está **desactivada**.
- [ ] Cambia la prioridad o el acceso de una: se guarda al momento. «Añadir plataforma» → elige otro
  portal: rellena nombre e id y una búsqueda de ejemplo.
- [ ] En la tarjeta de LinkedIn: el interruptor pide confirmación y avisa del riesgo; «Búsqueda
  pública sin sesión» también. No hace falta activarlos.

## 13. Plantillas

- [ ] **Mi CV**: «Subir mi CV» con un Word o PDF cualquiera (no el tuyo real si no quieres): queda
  «Pendiente de importar» con la petición para tu agente y «Copiar».
- [ ] **Todas las plantillas**: miniaturas con sus características (ATS, foto, columnas, motor).

## 14. Mi perfil

- [ ] **Contexto**: los cuatro ficheros (estilo, perfil conductual, criterios, narrativa) con el
  texto de Lucía. «Abrir carpeta» abre `data-demo/contexto/` (o enseña la ruta).
- [ ] **Muestras de estilo**: `carta-antigua.txt`, con «Ver texto extraído».
- [ ] **Documentos**: las carpetas con su número de ficheros (linkedin/ 1, empresas/ 2, estilo/ 1)
  y `salarios.csv`, la tabla que usa «Preparar negociación».

---

## 15. Con tu agente (opcional)

Con el agente arrancado sobre la demo (`CAI_DATA_DIR=data-demo`). Los botones de la UI abren tu
agente en una terminal con la orden escrita; también puedes pedírselo tú.

| Skill / botón | Con qué de la demo | Qué debe pasar |
|---|---|---|
| [ ] `process-jobs` / «Procesar ofertas» | Las 3 por extraer | Pasan a «Por revisar» o a «Cerrada» (filtros) |
| [ ] `assess-fit` / «Evaluar encaje» | Las 8 por revisar | «Valoración del agente» con veredicto y riesgos en cada una; la #3 no la valora como encaje perfecto |
| [ ] `generate-cv` / «Generar CV» | Una «Aprobada» (Bandeja → Aprobada) | CV redactado, verificado y renderizado; la oferta pasa a «CV listo» |
| [ ] `generate-cover-letter` | Ficha #2 | Carta con tus indicaciones, verificada (la #1 ya la trae) |
| [ ] `research-company` | Una «Enviada» | Bloque «Empresa» con dosier y fuentes (la #1 y la #2 ya lo traen) |
| [ ] `draft-message` | Ficha #1 | Borrador de LinkedIn para alguien de tu red |
| [ ] `prepare-interview` / «Preparar» | Una entrevista de «Próximos 7 días» | Plan de preparación por días en el hito |
| [ ] `mock-interview` / «Simulacro» | La misma | Simulacro pregunta a pregunta |
| [ ] `review-search` | Embudo | Retrospectiva sin tocar pesos ni filtros |
| [ ] «En segundo plano» | Flecha de «Procesar ofertas» | La página **Agente** enseña la ejecución, su progreso y su resultado (necesita `cai worker`, que arranca `cai start`) |
| [ ] «Dejar para mi próxima sesión» | Cualquier botón del agente | Encargo en **Agente → Para tu próxima sesión** (ya hay uno, «Generar CV»); `handle-requests` los atiende |

---

## 16. Volver a empezar

La demo se puede romper sin miedo: `uv run cai demo seed --force` la recrea desde cero. Para la
inglesa, añade `--lang en --dir data-demo-en`.

## Qué apuntar si algo falla

Página, qué hiciste, qué esperabas y qué pasó (con captura si puedes), el idioma de la UI y si
venía de `data-demo` o `data-demo-en`. Si sale un error, copia el mensaje completo.
