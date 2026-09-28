"""Resolución de las opciones de render: plantilla, foto, color y resto (CV_TEMPLATES §Opciones)."""

from pathlib import Path
from typing import Any

import pytest

from app.core.config import get_settings
from app.schemas.cv import CvRenderOptions
from app.services.documents import options, templates
from app.services.documents.options import OfferContext, detect_ats, detect_countries, resolve
from tests.cv_support import write_template
from tests.matching_support import demo_profile

ACCENT = {"accent_color": {"default": "#1F4E79", "choices": ["#1F4E79", "#2E7D32"]}}
PHOTO = {"photo": {"supported": True, "shape": "circle", "size_mm": 30}}


@pytest.fixture
def builtin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Plantillas integradas de prueba: `ats-simple` (fallback), `con-foto` y `color`."""
    root = tmp_path / "builtin"
    write_template(root, "ats-simple", origin="builtin")
    write_template(root, "con-foto", origin="builtin", ats_friendly=False, **PHOTO)
    write_template(
        root, "color", origin="builtin", options=ACCENT, page={"size": "Letter", "max_pages": 2}
    )
    monkeypatch.setattr(templates, "BUILTIN_TEMPLATES_DIR", root)
    return root


def offer(**changes: Any) -> OfferContext:
    data: dict[str, Any] = {"ats": None, "countries": ["ES"], "domain": None, "language": "es"}
    data.update(changes)
    return OfferContext.model_validate(data)


def cv_prefs(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "default_template": None,
        "photo_policy": {"default": True, "by_country": {"GB": False}},
        "template_rules": [],
    }
    base.update(changes)
    return {"cv": base}


def rules(*items: tuple[dict[str, Any], str]) -> list[dict[str, Any]]:
    return [{"when": when, "use": use} for when, use in items]


# --- Datos de la oferta ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://acme.wd3.myworkdayjobs.com/es/job/123", "workday"),
        ("https://myworkdayjobs.com/x", "workday"),
        ("https://boards.greenhouse.io/acme/jobs/1", "greenhouse"),
        ("https://jobs.sap.com/job/1", "successfactors"),
        ("jobs.lever.co/acme/1", "lever"),
        ("https://notworkday.com/x", None),
        ("https://example.com/myworkdayjobs.com", None),
        ("", None),
        (None, None),
    ],
)
def test_detect_ats_by_domain(url: str | None, expected: str | None) -> None:
    assert detect_ats(url) == expected


@pytest.mark.parametrize(
    ("locations", "expected"),
    [
        (["Madrid"], ["ES"]),
        (["A Coruña, España"], ["ES"]),
        (["Remoto, España"], ["ES"]),
        (["London, UK"], ["GB"]),
        (["Nueva York"], ["US"]),
        (["Dublín", "Ámsterdam"], ["IE", "NL"]),
        (["Remote"], []),
        (["Valencia"], []),  # ambigua: mejor no saber el país
        (["Madridejos"], []),  # palabra completa
    ],
)
def test_detect_countries(locations: list[str], expected: list[str]) -> None:
    assert detect_countries(locations) == expected


# --- Plantilla ------------------------------------------------------------------------------


def test_explicit_template_wins_over_rules(builtin: Path) -> None:
    profile = demo_profile(**cv_prefs(template_rules=rules(({"country": ["ES"]}, "con-foto"))))
    resolved = resolve(profile, CvRenderOptions(template_id="color"), offer(), False)
    assert (resolved.template_id, resolved.template_source) == ("color", "option")


def test_explicit_template_must_exist(builtin: Path) -> None:
    with pytest.raises(templates.TemplateNotFoundError, match="no existe"):
        resolve(demo_profile(**cv_prefs()), CvRenderOptions(template_id="nada"), offer(), False)


@pytest.mark.parametrize(
    ("when", "context"),
    [
        ({"ats": ["workday", "taleo"]}, {"ats": "workday"}),
        ({"country": ["GB", "ES"]}, {"countries": ["ES"]}),
        ({"domain": ["retail"]}, {"domain": "Retail y gran consumo"}),
        ({"domain": ["diseño"]}, {"domain": "Diseno"}),
        ({"language": ["en"]}, {"language": "en"}),
        ({"ats": ["workday"], "country": ["ES"]}, {"ats": "workday", "countries": ["ES"]}),
    ],
)
def test_rule_matches(builtin: Path, when: dict[str, Any], context: dict[str, Any]) -> None:
    profile = demo_profile(**cv_prefs(template_rules=rules((when, "color"))))
    resolved = resolve(profile, CvRenderOptions(), offer(**context), False)
    assert (resolved.template_id, resolved.template_source, resolved.rule_index) == (
        "color",
        "rule",
        0,
    )


@pytest.mark.parametrize(
    ("when", "context"),
    [
        ({"ats": ["workday"]}, {"ats": None}),
        ({"ats": ["workday"]}, {"ats": "greenhouse"}),
        ({"country": ["GB"]}, {"countries": ["ES"]}),
        ({"country": ["GB"]}, {"countries": []}),
        ({"domain": ["retail"]}, {"domain": None}),
        ({"domain": ["tail"]}, {"domain": "retail"}),
        ({"language": ["en"]}, {"language": "es"}),
        ({"ats": ["workday"], "country": ["ES"]}, {"ats": None, "countries": ["ES"]}),
    ],
)
def test_rule_does_not_match(builtin: Path, when: dict[str, Any], context: dict[str, Any]) -> None:
    profile = demo_profile(**cv_prefs(template_rules=rules((when, "color"))))
    resolved = resolve(profile, CvRenderOptions(), offer(**context), False)
    assert (resolved.template_id, resolved.template_source) == ("ats-simple", "fallback")


def test_first_matching_rule_wins(builtin: Path) -> None:
    profile = demo_profile(
        **cv_prefs(
            template_rules=rules(({"country": ["GB"]}, "con-foto"), ({"country": ["ES"]}, "color"))
            + rules(({"language": ["es"]}, "con-foto"))
        )
    )
    resolved = resolve(profile, CvRenderOptions(), offer(), False)
    assert (resolved.template_id, resolved.rule_index) == ("color", 1)


def test_rule_with_missing_template_warns_and_uses_default(builtin: Path) -> None:
    profile = demo_profile(
        **cv_prefs(
            default_template="con-foto", template_rules=rules(({"country": ["ES"]}, "no-existe"))
        )
    )
    resolved = resolve(profile, CvRenderOptions(), offer(), False)
    assert (resolved.template_id, resolved.template_source) == ("con-foto", "default_template")
    assert [w.code for w in resolved.warnings] == ["template_not_found"]


def test_default_template_when_no_rule_matches(builtin: Path) -> None:
    profile = demo_profile(**cv_prefs(default_template="color"))
    resolved = resolve(profile, CvRenderOptions(), offer(), False)
    assert (resolved.template_id, resolved.template_source) == ("color", "default_template")


def test_missing_default_template_falls_back_with_warning(builtin: Path) -> None:
    profile = demo_profile(**cv_prefs(default_template="clasica-foto"))
    resolved = resolve(profile, CvRenderOptions(), offer(), False)
    assert (resolved.template_id, resolved.template_source) == ("ats-simple", "fallback")
    assert [w.code for w in resolved.warnings] == ["template_not_found"]


def test_user_template_overrides_builtin(builtin: Path) -> None:
    write_template(get_settings().user_templates_dir, "ats-simple", name="La mía")
    template = templates.get("ats-simple")
    assert (template.meta.name, template.meta.origin) == ("La mía", "user")


# --- Foto -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("countries", "available", "expected"),
    [
        (["ES"], True, True),
        ([], True, True),  # país desconocido: `photo_policy.default`
        (["GB"], True, False),
        (["ES", "GB"], True, False),  # varios países: solo si todos la permiten
        (["ES"], False, False),  # sin foto
    ],
)
def test_photo_auto(builtin: Path, countries: list[str], available: bool, expected: bool) -> None:
    profile = demo_profile(**cv_prefs())
    resolved = resolve(
        profile, CvRenderOptions(template_id="con-foto"), offer(countries=countries), available
    )
    assert resolved.photo is expected
    assert resolved.warnings == []


def test_photo_auto_never_with_template_without_photo(builtin: Path) -> None:
    resolved = resolve(demo_profile(**cv_prefs()), CvRenderOptions(), offer(), True)
    assert resolved.photo is False


def test_photo_include_ignores_country_policy(builtin: Path) -> None:
    opts = CvRenderOptions(template_id="con-foto", photo="include")
    resolved = resolve(demo_profile(**cv_prefs()), opts, offer(countries=["GB"]), True)
    assert resolved.photo is True


@pytest.mark.parametrize(("template_id", "available"), [("ats-simple", True), ("con-foto", False)])
def test_photo_include_warns_when_impossible(
    builtin: Path, template_id: str, available: bool
) -> None:
    opts = CvRenderOptions(template_id=template_id, photo="include")
    resolved = resolve(demo_profile(**cv_prefs()), opts, offer(), available)
    assert resolved.photo is False
    assert [w.code for w in resolved.warnings] == ["photo_excluded"]


def test_photo_exclude(builtin: Path) -> None:
    opts = CvRenderOptions(template_id="con-foto", photo="exclude")
    assert resolve(demo_profile(**cv_prefs()), opts, offer(), True).photo is False


# --- Color y el resto -----------------------------------------------------------------------


def test_accent_color_defaults_to_template(builtin: Path) -> None:
    opts = CvRenderOptions(template_id="color")
    assert resolve(demo_profile(**cv_prefs()), opts, offer(), False).accent_color == "#1F4E79"


def test_accent_color_option_is_normalized(builtin: Path) -> None:
    opts = CvRenderOptions(template_id="color", accent_color="#2e7d32")
    assert resolve(demo_profile(**cv_prefs()), opts, offer(), False).accent_color == "#2E7D32"


@pytest.mark.parametrize(
    ("template_id", "match"), [("color", "admite estos colores"), ("ats-simple", "no admite")]
)
def test_accent_color_must_be_supported(builtin: Path, template_id: str, match: str) -> None:
    opts = CvRenderOptions(template_id=template_id, accent_color="#000000")
    with pytest.raises(options.InvalidRenderOptionsError, match=match):
        resolve(demo_profile(**cv_prefs()), opts, offer(), False)


def test_pages_and_size_come_from_template_unless_given(builtin: Path) -> None:
    profile = demo_profile(**cv_prefs())
    resolved = resolve(profile, CvRenderOptions(template_id="color"), offer(), False)
    assert (resolved.max_pages, resolved.page_size) == (2, "Letter")
    resolved = resolve(
        profile,
        CvRenderOptions(template_id="color", max_pages=1, page_size="A4"),
        offer(),
        False,
    )
    assert (resolved.max_pages, resolved.page_size) == (1, "A4")


def test_hidden_sections_without_repeats(builtin: Path) -> None:
    opts = CvRenderOptions(hidden_sections=["projects", "skills", "projects"])
    resolved = resolve(demo_profile(**cv_prefs()), opts, offer(), False)
    assert resolved.hidden_sections == ["projects", "skills"]
