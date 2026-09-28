"""Esquemas del CV: contenido (`CvContent`), opciones de render, verificación y plantillas.

Ver `docs/AGENT_INTERFACE.md` y `docs/CV_TEMPLATES.md`. El contenido lo escribe el agente y no sabe
nada del estilo; la presentación la deciden la plantilla (`TemplateMeta`) y las `CvRenderOptions`.
"""

import re
from typing import Annotated, Literal, Self, get_args

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.schemas.profile import Id

CvLanguage = Literal["es", "en"]
SectionName = Literal[
    "summary", "experience", "projects", "education", "certifications", "skills", "languages"
]
SECTIONS: tuple[str, ...] = get_args(SectionName)
PhotoMode = Literal["auto", "include", "exclude"]
PageSize = Literal["A4", "Letter"]
PhotoShape = Literal["circle", "square", "rounded"]
Engine = Literal["docx", "html"]

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _hex_color(value: str) -> str:
    if not _HEX_COLOR.match(value):
        raise ValueError("Color no válido: formato #RRGGBB (p. ej. #1F4E79).")
    return value.upper()


HexColor = Annotated[str, AfterValidator(_hex_color)]
Text = Annotated[str, Field(min_length=1)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Contenido (lo redacta el agente) -------------------------------------------------------


class CvBullet(_Strict):
    text: str = Field(min_length=1, max_length=400)
    evidence: list[Text] = Field(
        min_length=1, description="Ids de logros o elementos del perfil (`exp-acme/a2`)."
    )


class CvExperience(_Strict):
    experience_id: Id
    bullets: list[CvBullet] = Field(min_length=1, max_length=12)


class CvProject(_Strict):
    project_id: Id
    bullets: list[CvBullet] = Field(min_length=1, max_length=6)


class CvSkillGroup(_Strict):
    group: str = Field(min_length=1, max_length=60)
    items: list[Text] = Field(min_length=1, max_length=20)


class CvLanguageItem(_Strict):
    language: Text
    level: Text


class CvContent(_Strict):
    """Contenido de un CV, independiente de la plantilla (`docs/AGENT_INTERFACE.md`)."""

    language: CvLanguage
    subtitle: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1200)
    experience: list[CvExperience] = Field(min_length=1)
    projects: list[CvProject] = []
    skills: list[CvSkillGroup] = []
    education_ids: list[Id] = []
    certification_ids: list[Id] = []
    languages: list[CvLanguageItem] = []
    include_regional_language: bool = False
    keywords_targeted: list[Text] = []

    @model_validator(mode="after")
    def _no_repeated_ids(self) -> Self:
        for what, ids in (
            ("experience", [e.experience_id for e in self.experience]),
            ("projects", [p.project_id for p in self.projects]),
            ("education_ids", self.education_ids),
            ("certification_ids", self.certification_ids),
        ):
            repeated = sorted({i for i in ids if ids.count(i) > 1})
            if repeated:
                raise ValueError(f"`{what}` repite ids: {', '.join(repeated)}.")
        return self


# --- Opciones de render ---------------------------------------------------------------------


class CvRenderOptions(_Strict):
    """Presentación de un CV. `null`/`auto`: lo decide la app (`docs/CV_TEMPLATES.md` §Opciones)."""

    template_id: Id | None = None
    photo: PhotoMode = "auto"
    accent_color: HexColor | None = None
    max_pages: int | None = Field(default=None, ge=1, le=3)
    hidden_sections: list[SectionName] = []
    page_size: PageSize | None = None


# --- Verificación (la escribe el verificador) -----------------------------------------------


class VerificationIssue(_Strict):
    severity: Literal["blocker", "warning"]
    location: str = Field(min_length=1, max_length=200)
    problem: str = Field(min_length=1, max_length=1000)
    suggestion: str = Field(default="", max_length=1000)


class CvVerification(_Strict):
    passed: bool
    issues: list[VerificationIssue] = Field(default=[], max_length=50)

    @model_validator(mode="after")
    def _blockers_fail(self) -> Self:
        if self.passed and any(i.severity == "blocker" for i in self.issues):
            raise ValueError("`passed` no puede ser true si hay algún problema `blocker`.")
        return self


# --- Plantillas (`template.yaml`) -----------------------------------------------------------


class TemplateLayout(_Strict):
    columns: int = Field(default=1, ge=1, le=3)
    uses_tables: bool = False


class TemplatePhoto(_Strict):
    supported: bool = False
    shape: PhotoShape = "circle"
    size_mm: float = Field(default=30, ge=10, le=60)


class TemplatePage(_Strict):
    size: PageSize = "A4"
    max_pages: int = Field(default=1, ge=1, le=3)


class TemplateCapacity(_Strict):
    summary_chars: int = Field(default=450, ge=0)
    experience_bullets: int = Field(default=9, ge=0)
    skill_groups: int = Field(default=4, ge=0)


class AccentColorOption(_Strict):
    default: HexColor
    choices: list[HexColor] = Field(min_length=1)

    @model_validator(mode="after")
    def _default_in_choices(self) -> Self:
        if self.default not in self.choices:
            raise ValueError("`default` debe estar entre `choices`.")
        return self


class TemplateOptions(_Strict):
    accent_color: AccentColorOption | None = None


class TemplateMeta(_Strict):
    """`template.yaml` de una plantilla (`docs/CV_TEMPLATES.md` §Estructura)."""

    id: Id
    name: Text
    engine: Engine
    origin: Literal["builtin", "user"]
    source_file: str | None = None
    description: str = ""
    tags: list[str] = []
    layout: TemplateLayout = TemplateLayout()
    ats_friendly: bool
    photo: TemplatePhoto = TemplatePhoto()
    page: TemplatePage = TemplatePage()
    capacity: TemplateCapacity = TemplateCapacity()
    sections: list[SectionName] = Field(min_length=1)
    options: TemplateOptions = TemplateOptions()
    fonts: list[str] = []
    languages: list[CvLanguage] = ["es", "en"]
