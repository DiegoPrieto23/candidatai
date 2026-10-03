"""Esquemas de la carta de presentación (fase 08c, ADR-018).

El agente redacta `CoverLetterContent` (saludo, párrafos con evidencias y despedida) según las
indicaciones del usuario; el código pone el contacto, la fecha, el lugar y el nombre, y la
presenta con `CoverLetterRenderOptions`. La verificación reutiliza `CvVerification`.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.cv import CvLanguage, HexColor, PageSize, PhotoMode
from app.schemas.profile import MAX_LETTER_WORDS, Id

# Evidencias de un párrafo que no son ids del perfil (POLICIES §1, ADR-018).
EVIDENCE_EXTRACTION = "extraction"  # lo dice la oferta
EVIDENCE_USER = "user"  # lo dicen las indicaciones del usuario (las de la oferta o del perfil)

MAX_PARAGRAPHS = 6
MAX_INSTRUCTIONS = 4000

Evidence = Annotated[str, Field(min_length=1, max_length=200)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LetterParagraph(_Strict):
    text: str = Field(min_length=1, max_length=2000)
    evidence: list[Evidence] = Field(
        min_length=1,
        max_length=10,
        description="Ids del perfil (`exp-acme/a2`), `extraction` o `user`.",
    )


class CoverLetterContent(_Strict):
    """Carta que redacta el agente (`docs/AGENT_INTERFACE.md` §CoverLetterContent)."""

    language: CvLanguage
    recipient: str | None = Field(default=None, max_length=200)  # null = genérico
    greeting: str = Field(min_length=1, max_length=200)
    paragraphs: list[LetterParagraph] = Field(min_length=1, max_length=MAX_PARAGRAPHS)
    sign_off: str = Field(min_length=1, max_length=100)  # el nombre lo pone el código
    keywords_targeted: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default=[], max_length=30
    )


class CoverLetterRenderOptions(_Strict):
    """Presentación de la carta. `null`/`auto`: a juego con el render seleccionado del CV."""

    template_id: Id | None = None
    photo: PhotoMode = "auto"
    accent_color: HexColor | None = None
    page_size: PageSize | None = None


class CoverLetterBriefInput(_Strict):
    """Indicaciones de la carta para una oferta (las edita la UI o el agente)."""

    instructions: str = Field(default="", max_length=MAX_INSTRUCTIONS)
    max_words: int | None = Field(default=None, ge=50, le=MAX_LETTER_WORDS)
