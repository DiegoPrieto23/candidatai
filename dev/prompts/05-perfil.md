# Fase 05 · Perfil del candidato

## Contexto
Lee `demo/profile.example.yaml`, `docs/POLICIES.md` §1 y §4, y `docs/DATA_MODEL.md` §profile_versions.

## Objetivo
Un perfil estructurado, validado y versionado que sea la única fuente de verdad del candidato.

## Alcance
1. `app/schemas/profile.py`: `CandidateProfile` que valide exactamente la estructura de
   `demo/profile.example.yaml`: ids únicos, niveles `F|C+|C|B`, fechas `YYYY-MM` o `present`,
   evidencias que referencian ids existentes y `stories` STAR.
2. `app/services/profile.py`:
   - `load_from_yaml(path)` con errores que indiquen la ruta del campo (p. ej. `experience[1].achievements[0].id`);
   - `import_profile(path)`: crea una versión nueva solo si cambia el hash;
   - `current()`;
   - `public_view()`: sin teléfono, email ni `private`, que es lo que devuelve la MCP.
3. CLI: `jh profile validate [ruta]`, `jh profile import [ruta]`, `jh profile diff` (entre las dos
   últimas versiones) y `jh profile init`, que copia el ejemplo a `data/profile.yaml` si no existe.
4. Herramienta MCP `get_profile(sections?)` usando `public_view()`.
5. Resolución de evidencias: `resolve_evidence("exp-acme/a2") -> str` para el verificador.

## Fuera de alcance
Editor de perfil en la UI (más adelante, si compensa).

## Criterios de aceptación
- `jh profile validate demo/profile.example.yaml` pasa; tests con perfiles rotos y errores claros.
- Test de que `public_view()` nunca contiene teléfono, email ni datos de `private`.
- Importar el mismo fichero dos veces no crea una segunda versión.

## Al terminar
Actualiza `dev/ROADMAP.md`. Durante la fase usa solo `demo/profile.example.yaml`; el CV real del
usuario no se toca aquí. Al cerrar, sugiere al usuario ejecutar el skill `actualizar-perfil` con
su agente para crear su `data/profile.yaml` real a partir de su CV (no lo hagas tú dentro de esta
fase).
