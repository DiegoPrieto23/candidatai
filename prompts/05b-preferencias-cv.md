# Fase 05b · Preferencias de CV en el perfil

## Contexto
Ajuste pequeño tras añadir las plantillas de CV al kit. Lee `docs/CV_TEMPLATES.md` §Opciones de
render y `demo/profile.example.yaml` → `preferences.cv`. No hace falta leer más.

## Objetivo
Que `CandidateProfile` acepte las preferencias de CV nuevas, para que el perfil demo vuelva a
validar y los tests vuelvan a estar en verde, sin romper los `data/profile.yaml` ya creados.

## Alcance
1. `CvPreferences` (`app/schemas/profile.py`), manteniéndolo estricto:
   - `default_template: str | None = None` (id de plantilla; su existencia se comprueba en la fase 08);
   - `photo_file: str = "photo.jpg"`: ruta relativa dentro de `data/`; rechazar rutas absolutas y `..`;
   - `template_rules: list[TemplateRule] = []`, con `TemplateRule = {when: TemplateRuleWhen, use: str}`
     y `TemplateRuleWhen` con listas opcionales `ats`, `country` (ISO 3166-1 alfa-2 en mayúsculas),
     `domain` y `language`; al menos una informada;
   - `max_pages` sigue siendo opcional con su valor por defecto actual.
2. `public_view()`: incluye `preferences.cv` (el agente lo necesita para elegir plantilla). No hay
   nada privado en esa sección.
3. Tests: el perfil demo valida; un perfil con el bloque `cv` antiguo (solo `max_pages` y
   `photo_policy`) sigue validando; una regla sin condiciones falla; `photo_file` con `..` falla;
   un país en minúsculas falla con un error legible.

## Fuera de alcance
Resolver qué plantilla toca a cada oferta (fase 08).

## Criterios de aceptación
- `uv run pytest` en verde y `uv run jh profile validate ../demo/profile.example.yaml` pasa.
- `uv run jh profile validate` sobre `data/profile.yaml` sigue pasando sin tocarlo.

## Al terminar
Actualiza `docs/ROADMAP.md` (fila 05b y registro) y propón mensaje de commit.
