"""Guía de preparación de una entrevista. La redacta el agente con `prepare-interview`
como contenido estructurado; la app la maqueta y la imprime a PDF (`services/interview_guide.py`).

El agente no escribe HTML: solo texto en bloques tipados. En el texto valen `**negrita**`,
`*cursiva*` y `` `código` ``; todo lo demás se escapa al maquetar.
"""

import re
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

MAX_SECTIONS = 30
MAX_BLOCKS = 60
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_URL = re.compile(r"^https?://[^\s<>\"']+$")

Language = Literal["es", "en"]


def _hex(value: str) -> str:
    if not _HEX.fullmatch(value):
        raise ValueError("Un color en hexadecimal de 6 cifras, p. ej. `#0082C3`.")
    return value.upper()


def _url(value: str) -> str:
    if not _URL.fullmatch(value):
        raise ValueError("Una URL pública que empiece por http:// o https://.")
    return value


HexColor = Annotated[str, AfterValidator(_hex)]
PublicUrl = Annotated[str, AfterValidator(_url)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --- Bloques --------------------------------------------------------------------------------


class ParagraphBlock(_Strict):
    type: Literal["paragraph"]
    text: str = Field(min_length=1, max_length=4000, description="Párrafo; `\n\n` lo parte.")


class HeadingBlock(_Strict):
    type: Literal["heading"]
    text: str = Field(min_length=1, max_length=200, description="Subtítulo dentro de la sección.")


class Bullet(_Strict):
    label: str | None = Field(
        default=None, max_length=150, description="Lo que va en negrita delante (opcional)."
    )
    text: str = Field(min_length=1, max_length=1500)


class BulletsBlock(_Strict):
    type: Literal["bullets"]
    items: list[Bullet] = Field(min_length=1, max_length=40)


class TableBlock(_Strict):
    type: Literal["table"]
    headers: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(
        min_length=2, max_length=5
    )
    rows: list[list[Annotated[str, Field(max_length=800)]]] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def _same_width(self) -> "TableBlock":
        wrong = [i + 1 for i, row in enumerate(self.rows) if len(row) != len(self.headers)]
        if wrong:
            raise ValueError(
                f"Las filas {', '.join(map(str, wrong))} no tienen {len(self.headers)} celdas, "
                "como la cabecera."
            )
        return self


class QaItem(_Strict):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(
        min_length=1,
        max_length=3000,
        description="Idea de respuesta: solo hechos del perfil, con la historia que usar.",
    )
    caution: str | None = Field(
        default=None, max_length=600, description="«Ojo»: qué no decir o qué no tienes."
    )


class QaBlock(_Strict):
    type: Literal["qa"]
    items: list[QaItem] = Field(min_length=1, max_length=25)


class CalloutBlock(_Strict):
    type: Literal["callout"]
    tone: Literal["tip", "warning", "note"] = Field(
        description="`tip`: consejo; `warning`: «Ojo» (un punto flojo, algo que no decir); "
        "`note`: aclaración."
    )
    text: str = Field(min_length=1, max_length=1500)


class CodeColumn(_Strict):
    label: str = Field(min_length=1, max_length=60, description="P. ej. «SQL» o «PySpark».")
    code: str = Field(min_length=1, max_length=3000)


class CodeBlock(_Strict):
    type: Literal["code"]
    title: str | None = Field(default=None, max_length=200)
    columns: list[CodeColumn] = Field(
        min_length=1, max_length=2, description="Una columna, o dos para compararlas lado a lado."
    )
    caption: str | None = Field(default=None, max_length=600)


GuideBlock = Annotated[
    ParagraphBlock | HeadingBlock | BulletsBlock | TableBlock | QaBlock | CalloutBlock | CodeBlock,
    Field(discriminator="type"),
]


# --- Guía -----------------------------------------------------------------------------------


class GuideSection(_Strict):
    title: str = Field(min_length=1, max_length=150, description="Título, sin numerar.")
    blocks: list[GuideBlock] = Field(min_length=1, max_length=MAX_BLOCKS)


class GuideSource(_Strict):
    title: str = Field(min_length=1, max_length=200)
    url: PublicUrl


class InterviewGuideInput(_Strict):
    language: Language = Field(
        description="Idioma de la guía (y de los textos fijos del PDF): el que pida el usuario; "
        "si no, el de la entrevista; si no consta, en el que te escribe."
    )
    title: str = Field(
        min_length=1, max_length=150, description="El puesto, p. ej. «Data Analyst»."
    )
    subtitle: str | None = Field(
        default=None,
        max_length=300,
        description="Para qué entrevista es, p. ej. «Entrevista técnica con el equipo de datos».",
    )
    accent_color: HexColor = Field(
        default="#0F766E",
        description="Color principal de la marca de la empresa (de su web), en hexadecimal.",
    )
    sections: list[GuideSection] = Field(min_length=3, max_length=MAX_SECTIONS)
    sources: list[GuideSource] = Field(
        default_factory=list, max_length=40, description="Webs consultadas, con su URL."
    )


class GuideInfo(BaseModel):
    """Lo que enseña la ficha de la guía guardada (el contenido se queda en el hito)."""

    file: str  # nombre del PDF dentro de `entrevistas/`
    language: Language
    title: str
    saved_at: datetime
    agent_name: str | None = None


def guide_info(prep_guide: dict[str, Any] | None) -> GuideInfo | None:
    """La guía guardada en el hito (`milestones.prep_guide`), sin el contenido."""
    if not prep_guide:
        return None
    guide = prep_guide.get("guide") or {}
    return GuideInfo(
        file=prep_guide["file"],
        language=guide.get("language", "es"),
        title=guide.get("title", ""),
        saved_at=prep_guide["saved_at"],
        agent_name=prep_guide.get("agent_name"),
    )
