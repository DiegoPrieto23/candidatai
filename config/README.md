# `config/`

Reglas y listas **genéricas** de la app. Van en git y no llevan datos personales: lo tuyo vive en
`data/` (perfil, contexto, documentos) y en `.env`. El código las lee de aquí
(`backend/app/core/policies.py`); si editas una, el cambio vale para cualquiera que use el
repositorio.

| Fichero | Qué es | Quién lo cambia |
|---|---|---|
| `policies.yaml` | Deduplicación, filtros duros, pesos y umbral del score, CV, carta, conectores, alertas, búsqueda con navegador, seguimientos, calendario y candidatura asistida (`docs/POLICIES.md`) | Tú, a mano. Los pesos y el umbral se ajustan con `jh eval matching` |
| `skill_aliases.yaml` | Sinónimos de skills → nombre canónico, para que «PySpark» cuente como «Apache Spark» en el matching y en las comprobaciones del CV | Tú, a mano, o la página **Skills** con «Es lo mismo que…» (fase 14) |
| `title_aliases.yaml` | Puestos escritos de otra forma (sobre todo en español) → su nombre en inglés, para comparar títulos con `preferences.roles` | Tú, a mano |
| `countries.yaml` | País de una oferta a partir de su ubicación (reglas de plantilla y política de foto) | Tú, a mano |
| `injection_patterns.yaml` | Frases de posible inyección de instrucciones en ofertas (ADR-012) | Tú, a mano |

## `skill_aliases.yaml`

Formato: `Nombre canónico: [sinónimo, otro sinónimo]`. Se compara sin tildes, mayúsculas ni signos
(salvo `+` y `#`, por C++ y C#). Un sinónimo solo puede apuntar a un canónico.

**Desde la UI** (página «Skills», ADR-026): cuando una skill que piden tus ofertas es otra forma de
llamar a una de tu perfil, «Es lo mismo que…» la añade como sinónimo:

- en la entrada de esa skill si ya existe (también si tu perfil la llama por un sinónimo: si tienes
  «PySpark», va a «Apache Spark»); si no, en una entrada nueva al final con el nombre de tu perfil;
- conservando comentarios, orden, comillas y fin de línea del fichero (ruamel.yaml);
- nunca si el nombre ya es sinónimo de otra skill o tu perfil ya lo cubre: eso lo cambias a mano.

Cambiar este fichero (a mano o desde la UI) cambia el `scoring_key`: el worker recalcula los
matches de las ofertas abiertas sin reiniciarse. Lo añadido desde la UI aparece como cambio en git;
confírmalo si quieres conservarlo (un `git checkout` del fichero lo deshace). La UI no borra alias:
si te equivocas, edita el fichero.
