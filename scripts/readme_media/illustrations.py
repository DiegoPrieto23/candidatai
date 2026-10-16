"""Genera los SVG del README (banner y «cómo funciona») en inglés y español."""

import sys
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(sys.argv[1])
FONT = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
MONO = "'Cascadia Code', Consolas, 'SF Mono', monospace"

TEXT = {
    "en": {
        "tagline": "Your job search, end to end, on your own machine.",
        "sub": "Your AI agent does the thinking. The app keeps the state, the rules and the checks.",
        "steps": ["Find", "Triage", "Tailor CV", "Apply", "Follow up", "Offer"],
        "how_title": "How it works",
        "lanes": ["You", "Your AI agent", "CandidatAI"],
        "cards": [
            # (paso, quién: 0 tú, 1 agente, 2 app, título, detalle)
            ("1", 2, "Jobs come in", "ATS APIs, email alerts,\nbrowser button, portals"),
            ("2", 1, "Extract & assess", "structured data and a\nreasoned fit verdict"),
            ("3", 0, "Triage", "approve or discard with\nan explained 0-100 score"),
            ("4", 1, "Write the CV", "every line cites evidence\nfrom your profile"),
            ("5", 2, "Verify & render", "independent check, your\ntemplate, PDF in seconds"),
            ("6", 0, "Apply", "the app fills the form;\nonly you press Send"),
            ("7", 2, "Track", "kanban, follow-ups,\ninterviews, funnel"),
        ],
        "foot": "The app never calls an LLM · nothing leaves without your confirmation · your data stays in data/",
    },
    "es": {
        "tagline": "Tu búsqueda de empleo, de principio a fin, en tu equipo.",
        "sub": "Tu agente de IA pone el criterio. La app guarda el estado, las reglas y las comprobaciones.",
        "steps": ["Buscar", "Triar", "CV a medida", "Postular", "Seguir", "Oferta"],
        "how_title": "Cómo funciona",
        "lanes": ["Tú", "Tu agente de IA", "CandidatAI"],
        "cards": [
            ("1", 2, "Entran ofertas", "APIs de ATS, alertas por\ncorreo, botón, portales"),
            ("2", 1, "Extrae y valora", "datos estructurados y\nuna valoración razonada"),
            ("3", 0, "Triaje", "apruebas o descartas con\nun score 0-100 explicado"),
            ("4", 1, "Redacta el CV", "cada línea cita su\nevidencia de tu perfil"),
            ("5", 2, "Verifica y renderiza", "comprobación independiente,\ntu plantilla, PDF en segundos"),
            ("6", 0, "Candidatura", "la app rellena el formulario;\nsolo tú pulsas Enviar"),
            ("7", 2, "Seguimiento", "kanban, seguimientos,\nentrevistas, embudo"),
        ],
        "foot": "La app nunca llama a un LLM · nada sale sin tu confirmación · tus datos se quedan en data/",
    },
}

TEAL = "#0F766E"  # docs/brand
TEAL_LIGHT = "#5EEAD4"


def banner(lang: str) -> str:
    t = TEXT[lang]
    w, h = 1280, 360
    chips = []
    x = 96
    for i, step in enumerate(t["steps"]):
        width = 34 + 10.5 * len(step)
        chips.append(
            f'<g transform="translate({x:.0f},262)">'
            f'<rect width="{width:.0f}" height="40" rx="20" fill="#ffffff" fill-opacity="0.12" '
            f'stroke="#ffffff" stroke-opacity="0.35"/>'
            f'<text x="{width / 2:.0f}" y="26" text-anchor="middle" font-size="17" '
            f'font-weight="600" fill="#ffffff">{escape(step)}</text></g>'
        )
        x += width
        if i < len(t["steps"]) - 1:
            chips.append(
                f'<path d="M{x + 8:.0f} 282 h18 m-6 -6 l6 6 l-6 6" stroke="{TEAL_LIGHT}" '
                f'stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            )
            x += 34
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="CandidatAI — {escape(t['tagline'])}">
  <rect width="{w}" height="{h}" rx="20" fill="{TEAL}"/>
  <g font-family="{FONT}">
    <g transform="translate(96,66) scale(1.25)">
      <rect width="64" height="64" rx="14" fill="#ffffff"/>
      <path d="M12 64 C12 47 20.5 40.5 32 40.5 C43.5 40.5 52 47 52 64 Z" fill="{TEAL}"/>
      <polygon points="32.00,9.40 34.74,11.76 38.30,11.09 39.50,14.50 42.91,15.70 42.24,19.26 44.60,22.00 42.24,24.74 42.91,28.30 39.50,29.50 38.30,32.91 34.74,32.24 32.00,34.60 29.26,32.24 25.70,32.91 24.50,29.50 21.09,28.30 21.76,24.74 19.40,22.00 21.76,19.26 21.09,15.70 24.50,14.50 25.70,11.09 29.26,11.76" fill="{TEAL}" stroke="{TEAL}" stroke-width="2.6" stroke-linejoin="round"/>
      <path d="M26.4 21.6 L30.4 25.6 L37.8 18.2" fill="none" stroke="#ffffff" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>
    </g>
    <text x="196" y="122" font-size="64" font-weight="700" fill="#ffffff" letter-spacing="-1.6">Candidat<tspan fill="{TEAL_LIGHT}">AI</tspan></text>
    <text x="96" y="194" font-size="28" font-weight="600" fill="#ffffff">{escape(t['tagline'])}</text>
    <text x="96" y="230" font-size="19" fill="#D7F2EE">{escape(t['sub'])}</text>
    {''.join(chips)}
  </g>
  <g transform="translate(1010,110)" font-family="{MONO}" font-size="15" fill="#D7F2EE" fill-opacity="0.9">
    <rect x="-24" y="-34" width="230" height="132" rx="12" fill="#06201E" fill-opacity="0.55" stroke="#ffffff" stroke-opacity="0.15"/>
    <text y="0"><tspan fill="{TEAL_LIGHT}">$</tspan> cai status</text>
    <text y="26">pending_triage  <tspan fill="#ffffff">8</tspan></text>
    <text y="50">cv_ready        <tspan fill="#ffffff">2</tspan></text>
    <text y="74">in_process      <tspan fill="#ffffff">6</tspan></text>
  </g>
</svg>
"""


LANE_COLORS = [
    ("#FEF3C7", "#B45309", "#92400E"),  # tú: ámbar
    ("#EDE9FE", "#6D28D9", "#5B21B6"),  # agente: violeta
    ("#D5F0EC", TEAL, "#0B4F4B"),  # app: verde azulado
]
LANE_ICONS = [
    # persona
    '<circle cx="0" cy="-6" r="6" fill="none" stroke="currentColor" stroke-width="2"/>'
    '<path d="M-10 10 a10 9 0 0 1 20 0" fill="none" stroke="currentColor" stroke-width="2"/>',
    # chispa (agente)
    '<path d="M0 -12 L3 -3 L12 0 L3 3 L0 12 L-3 3 L-12 0 L-3 -3 Z" fill="currentColor"/>',
    # caja (app)
    '<rect x="-10" y="-10" width="20" height="20" rx="4" fill="none" stroke="currentColor" stroke-width="2"/>'
    '<path d="M-10 -3 h20" stroke="currentColor" stroke-width="2"/>',
]


def how(lang: str) -> str:
    t = TEXT[lang]
    w, h = 1400, 520
    lane_y = [96, 226, 356]
    lane_h = 112
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{escape(t["how_title"])}">',
        "<style>"
        ".bg{fill:#ffffff}.title{fill:#18181B}.muted{fill:#52525B}.card{fill:#ffffff;stroke:#E4E4E7}"
        ".arrow{stroke:#A1A1AA}.lanelabel{fill:#3F3F46}"
        "@media (prefers-color-scheme: dark){.bg{fill:#0D1117}.title{fill:#F4F4F5}.muted{fill:#A1A1AA}"
        ".card{fill:#161B22;stroke:#30363D}.arrow{stroke:#6E7681}.lanelabel{fill:#D4D4D8}"
        ".lane{fill-opacity:0.10}.cardtitle{fill:#F4F4F5}.carddetail{fill:#A1A1AA}}"
        "</style>",
        f'<rect class="bg" width="{w}" height="{h}" rx="16"/>',
        f'<g font-family="{FONT}">',
        f'<text class="title" x="40" y="56" font-size="28" font-weight="800">{escape(t["how_title"])}</text>',
    ]
    for i, (fill, stroke, _text) in enumerate(LANE_COLORS):
        y = lane_y[i]
        parts.append(
            f'<rect class="lane" x="24" y="{y}" width="{w - 48}" height="{lane_h}" rx="14" '
            f'fill="{fill}" fill-opacity="0.55"/>'
        )
        parts.append(
            f'<g transform="translate(64,{y + lane_h / 2:.0f})" color="{stroke}" style="color:{stroke}">'
            f"{LANE_ICONS[i]}</g>"
        )
        parts.append(
            f'<text class="lanelabel" x="88" y="{y + lane_h / 2 + 6:.0f}" font-size="17" '
            f'font-weight="700">{escape(t["lanes"][i])}</text>'
        )
    card_w, card_h = 156, 92
    x0, step = 214, 166
    centers = []
    for n, (num, lane, title, detail) in enumerate(t["cards"]):
        x = x0 + n * step
        y = lane_y[lane] + (lane_h - card_h) / 2
        stroke = LANE_COLORS[lane][1]
        centers.append((x, y, lane))
        lines = detail.split("\n")
        parts.append(
            f'<g transform="translate({x},{y:.0f})">'
            f'<rect class="card" width="{card_w}" height="{card_h}" rx="10" stroke-width="1.5"/>'
            f'<rect width="5" height="{card_h}" rx="2.5" fill="{stroke}"/>'
            f'<circle cx="22" cy="20" r="11" fill="{stroke}"/>'
            f'<text x="22" y="25" text-anchor="middle" font-size="13" font-weight="700" fill="#fff">{num}</text>'
            f'<text class="title cardtitle" x="40" y="25" font-size="13.5" font-weight="700">{escape(title)}</text>'
            + "".join(
                f'<text class="muted carddetail" x="14" y="{52 + 17 * k}" font-size="11">{escape(line)}</text>'
                for k, line in enumerate(lines)
            )
            + "</g>"
        )
    for (x1, y1, l1), (x2, y2, l2) in zip(centers, centers[1:]):
        # En ángulo: baja (o sube) desde el borde de la tarjeta y entra por la izquierda de la siguiente.
        sx = x1 + card_w - 28
        sy = y1 + card_h if l2 > l1 else y1
        ex, ey = x2, y2 + card_h / 2
        parts.append(
            f'<path class="arrow" d="M{sx:.0f} {sy:.0f} V{ey - (8 if l2 > l1 else -8):.0f} '
            f'Q{sx:.0f} {ey:.0f} {sx + 8:.0f} {ey:.0f} H{ex - 4:.0f}" fill="none" stroke-width="2"/>'
            f'<path class="arrow" d="M{ex - 11:.0f} {ey - 5:.0f} L{ex - 4:.0f} {ey:.0f} L{ex - 11:.0f} {ey + 5:.0f}" '
            f'fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        )
    parts.append(
        f'<text class="muted" x="{w / 2:.0f}" y="{h - 22}" text-anchor="middle" font-size="14">'
        f'{escape(t["foot"])}</text>'
    )
    parts.append("</g></svg>\n")
    return "\n".join(parts)


OUT.mkdir(parents=True, exist_ok=True)
for lang in ("en", "es"):
    (OUT / f"banner-{lang}.svg").write_text(banner(lang), encoding="utf-8")
    name = "how-it-works" if lang == "en" else "como-funciona"
    (OUT / f"{name}-{lang}.svg").write_text(how(lang), encoding="utf-8")
print("ok")
