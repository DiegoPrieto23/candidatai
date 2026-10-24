# Fase 28.1 · Auditoría del repo público y primera release

Fecha: 2026-10-23. Agente: Claude Code (Opus 5.5). Rama `fase/28-lanzamiento-repo`.

## 1. Secretos en todo el historial

Sobre un espejo local con **todas** las ramas, locales y de `origin` (59 referencias, 148 commits):

| Herramienta | Orden | Resultado |
|---|---|---|
| gitleaks v8.21.2 (Docker) | `gitleaks git <espejo> --log-opts=--all --redact` | **Sin hallazgos** (104 commits con cambios; los de fusión no aportan diff) |
| trufflehog 3.88.0 (Docker) | `trufflehog git file://<clon con todas las ramas>` | 1 hallazgo **sin verificar**: falso positivo |

El hallazgo de trufflehog (detector `URI`) es `backend/tests/test_cli_profile.py:86`: una URL de
prueba con `usuario:secreto@pypi.org` que el test usa para comprobar que el perfil **rechaza**
fuentes con credenciales. No es ninguna credencial real y no hay nada que revocar.

`.env` y `data/` nunca entraron en git (`.gitignore` desde la fase 01).

## 2. Datos personales en lo versionado

Se buscaron en el árbol actual (`git grep`) y en todo el historial (`git log --all -S` y `-G -i`)
el nombre completo, el correo, el teléfono, el perfil de LinkedIn y los cinco empleadores de
`data/profile.yaml` (los términos no se copian aquí).

- **Teléfono, correo, LinkedIn y empleadores:** 0 apariciones en el árbol y en el historial.
- **Nombre:** solo el nombre corto, en la licencia y en el pie del README (`© 2026 …`), a propósito.
- **Ciudad:** la de la demo (A Coruña) es un dato de fixture de la candidata ficticia.
- **Correos en docs y demo:** solo de ejemplo (`*.example`, `tu.correo@gmail.com`) y remitentes
  genéricos de portales.
- **URLs de ofertas:** ninguna real (solo `acme/jobs/123` y similares).
- **Capturas, GIF y vídeos** (`docs/img`, `docs/video`, fase 23.5b): revisados a ojo; todos salen
  de la demo (banner «Modo demo: datos ficticios», candidata Lucía Varela Otero, empresas
  inventadas).
- **`dev/pruebas/`:** los textos que hablan de «datos reales» son guías de prueba (qué hacer con
  tu perfil), no resultados con datos.

## 3. Correo de los commits

Los 148 commits llevan el correo personal del autor, ya público. Decisión del usuario
(2026-10-23): **no se reescribe el historial**. Desde ahora, el repo usa el correo noreply de
GitHub de la cuenta (`git config user.email` local).

Pendiente del usuario (no está en la API): GitHub → Settings → Emails → marcar «Keep my email
addresses private» y «Block command line pushes that expose my email».

## 4. Ajustes de seguridad de GitHub

Activados por `gh api` el 2026-10-23:

| Ajuste | Estado |
|---|---|
| Secret scanning | ✅ |
| Push protection | ✅ |
| Dependabot alerts | ✅ |
| Dependabot security updates | ✅ |
| Private vulnerability reporting | ✅ |
| Patrones genéricos y comprobación de validez | ❌ requieren GitHub Advanced Security |

En el repo: `.github/dependabot.yml` (uv, pnpm y Actions, semanal y agrupado),
`.github/CODEOWNERS` y `SECURITY.md` con el enlace al aviso privado.

## 5. Release `v0.1.0`

Ver `fase-28.1-prueba-manual.md` para la prueba en seco, la etiqueta y los instaladores.
