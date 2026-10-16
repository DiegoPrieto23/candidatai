---
name: review-linkedin
description: Revisa el perfil de LinkedIn del candidato frente a su perfil de CandidatAI y a las ofertas que aprueba, y genera un informe de cambios propuestos que él aplica a mano. Úsalo cuando se pida revisar, mejorar u optimizar el perfil de LinkedIn. Antes se llamaba revisar-linkedin.
---

<!-- GENERADO por scripts/sync_agents.py desde .agents/skills/review-linkedin/SKILL.md. No editar a mano: edita la fuente y regenera. -->

Sigue `docs/POLICIES.md` §1, §4, §5 y §7. El agente **nunca entra en LinkedIn**: ni navega, ni
inicia sesión, ni edita nada allí. Propone; el usuario aplica.

## 1. Reunir el material
1. `get_profile()`: es la fuente de verdad. Si aún no hay perfil, para y sugiere antes el skill
   `update-profile`.
2. Pide el perfil actual de LinkedIn de una de estas formas (lo que prefiera el usuario):
   - el PDF que genera LinkedIn desde su propio perfil («Más» → «Guardar en PDF»), guardado en
     `data/documentos/linkedin/`;
   - el texto de cada sección pegado en el chat: titular, «Acerca de», experiencia, formación,
     aptitudes, idiomas y certificaciones.
3. Qué demanda el mercado que le interesa: `list_jobs(stage="approved", limit=30)` y, para cada
   una, `get_extraction`. Cuenta las `must_have_skills` y `nice_to_have_skills` más repetidas y
   los títulos normalizados más frecuentes. Si hay menos de 5 ofertas aprobadas, usa también
   `preferences.roles` del perfil y dilo en el informe.

## 2. Comparar sección por sección
- **Titular**: identidad profesional estable y tecnologías clave, coherente con `headline`.
  Nunca el título de una oferta concreta.
- **Acerca de**: versión para LinkedIn de `summary`, en primera persona, con las keywords más
  demandadas **que el perfil respalda**, un logro con métrica real y una línea final de qué busca.
  Sin clichés (§7).
- **Experiencia**: mismos puestos, empresas y fechas que el perfil. Por puesto, 2-4 logros
  elegidos de `achievements` y las aptitudes de cada uno. Proyectos con `nda: true`, a alto nivel.
- **Aptitudes**: primero las de nivel F y C+ más demandadas en las ofertas aprobadas; señala
  cuáles destacar arriba. Nunca propongas añadir `basic_skills` ni skills de nivel B.
- **Formación, certificaciones e idiomas**: al día y con los mismos datos que el perfil.
- **Datos de contacto**: sin teléfono en el perfil público. La URL personalizada debe ser la
  misma que aparece en el CV.
- **Incoherencias**: todo dato que no coincida entre LinkedIn y el perfil (fechas, cargos,
  cifras). No asumas cuál es el correcto: pregunta y, si lo que falla es el perfil, corrígelo con
  `update-profile`.

Límites de longitud a tener en cuenta (pueden cambiar; si LinkedIn rechaza un texto, recórtalo):
titular unos 220 caracteres y «Acerca de» unos 2.600.

## 3. Entregar el informe
Escribe `data/documentos/linkedin/informe-<AAAA-MM-DD>.md` con:
1. **Resumen**: los 3 cambios de mayor impacto y por qué, con datos (p. ej. «Snowflake aparece en
   14 de 20 ofertas aprobadas y no está en tus aptitudes»).
2. **Cambios por sección**, ordenados por impacto. Para cada uno: texto actual, texto propuesto
   **listo para copiar** y motivo en una línea.
3. **Keywords**: tabla de las más demandadas con `sí/no` en LinkedIn y en el perfil, y cuáles no
   puedes usar porque el perfil no las respalda.
4. **Preguntas pendientes**: incoherencias o huecos que solo puede resolver el usuario.
5. **Checklist** para aplicar los cambios a mano.

Idioma del informe: el de la conversación. Idioma de los textos propuestos: el del perfil de
LinkedIn actual; si el usuario busca ofertas en inglés, ofrece también la versión en inglés del
titular y del «Acerca de».

## 4. Cerrar
- Presenta el resumen y los cambios **de uno en uno** si el usuario quiere revisarlos en el chat.
  Un «sí» a un cambio no vale para los demás.
- El informe fechado en `data/documentos/linkedin/` es el registro de la revisión (no es un evento de
  ninguna oferta, así que no uses `add_event`).
- Si el usuario confirma que ya aplicó los cambios, ofrece borrar los informes antiguos de
  `data/documentos/linkedin/` y conservar solo el último.
