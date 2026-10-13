# Security

**English** · [Español](#seguridad)

## Reporting a vulnerability

Please **don't open a public issue** for security problems. Use GitHub's private vulnerability
reporting ("Security" tab → "Report a vulnerability") or contact the maintainer through their
GitHub profile. Include the steps to reproduce it with the demo data.

## Threat model in short

CandidatAI runs locally and reads untrusted text all the time (job postings, emails, websites) that
an AI agent then reads too. Its defences live in code, so they hold whatever agent you use
([ADR-012](docs/DECISIONS.md)):

- **Prompt injection:** hidden text and phrases aimed at an AI are detected when a job is stored
  and flagged in the UI; the agent receives postings wrapped and marked as untrusted, and the role
  that reads them has the minimum tools.
- **No sending:** the agent interface can't submit forms or send email. Submitting an application
  takes a single-use token that only the UI produces after you confirm.
- **Validation:** everything the agent returns goes through strict schemas; CV claims must cite
  evidence that exists in your profile.
- **Local only:** the API listens on `127.0.0.1`. Downloads refuse local and private addresses,
  also after redirects. Your data stays in `data/`, outside git.

Known residual risks are documented in [`docs/POLICIES.md`](docs/POLICIES.md) and
[`docs/FUENTES_OFERTAS.md`](docs/FUENTES_OFERTAS.md). The main one: the local API has no
authentication, so an agent with terminal access could call it directly.

---

## Seguridad

[English](#security) · **Español**

### Avisar de una vulnerabilidad

Por favor, **no abras un issue público** para un problema de seguridad. Usa el aviso privado de
vulnerabilidades de GitHub (pestaña «Security» → «Report a vulnerability») o escribe al mantenedor
desde su perfil de GitHub. Incluye los pasos para reproducirlo con los datos de la demo.

### El modelo de amenazas, en corto

CandidatAI se ejecuta en local y lee continuamente texto no confiable (ofertas, correos, webs) que
luego también lee un agente de IA. Sus defensas están en el código, así que valen con cualquier
agente ([ADR-012](docs/DECISIONS.md)):

- **Inyección de instrucciones:** el texto oculto y las frases dirigidas a una IA se detectan al
  guardar la oferta y se avisan en la UI; el agente recibe las ofertas envueltas y marcadas como no
  confiables, y el rol que las lee tiene las herramientas mínimas.
- **Nada se envía:** la interfaz para agentes no puede enviar formularios ni correos. Enviar una
  candidatura exige un token de un solo uso que solo genera la UI tras tu confirmación.
- **Validación:** todo lo que devuelve el agente pasa por esquemas estrictos; cada afirmación del
  CV tiene que citar una evidencia que exista en tu perfil.
- **Solo en local:** la API escucha en `127.0.0.1`. Las descargas rechazan direcciones locales y
  privadas, también tras una redirección. Tus datos se quedan en `data/`, fuera de git.

Los riesgos residuales conocidos están en [`docs/POLICIES.md`](docs/POLICIES.md) y
[`docs/FUENTES_OFERTAS.md`](docs/FUENTES_OFERTAS.md). El principal: la API local no tiene
autenticación, así que un agente con acceso a la terminal podría llamarla directamente.
