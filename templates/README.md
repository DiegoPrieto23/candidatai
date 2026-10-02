# Plantillas integradas

Plantillas de CV genéricas que vienen con el proyecto. No contienen datos personales: sus
previsualizaciones (`preview.pdf` y `preview.png`) se generan con el perfil ficticio de `demo/` y
su foto, `demo/photo.png`, una silueta dibujada por el script (nunca una persona real).

Se crean en las fases 08 (`ats-simple`, `clasica-foto`) y 08b (`moderna-2col`). Las docx se
generan por código, de forma reproducible, con `scripts/build_builtin_templates.py` (no se
editan a mano): `uv run --directory backend python ../scripts/build_builtin_templates.py`. Las
html (`moderna-2col`) se escriben a mano (`template.html`, `style.css`) y el script solo
regenera su preview. `moderna-2col/fonts/` trae Lato (subconjuntos latin y latin-ext en woff2,
de Google Fonts) con su licencia SIL Open Font License en `OFL.txt`. Tus plantillas
van en `data/templates/`, fuera del repositorio. Formato, contrato de variables y opciones:
`docs/CV_TEMPLATES.md`.
