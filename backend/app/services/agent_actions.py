"""Catálogo cerrado de acciones «en tu agente» (ADR-024): la orden de cada una, dónde se puede
lanzar y con qué herramientas en segundo plano. Lo usan `agent_launch`, `agent_runs`,
`agent_requests` y `agent_prefs` (fase 24.4), que lo importan de aquí para no depender unos de
otros.
"""

from dataclasses import dataclass
from typing import Literal

from app.services.pipeline import Stage

ActionId = Literal[
    "search-jobs",
    "process-jobs",
    "assess-fit",
    "generate-cv",
    "add-skills",
    "training-plan",
    "review-replies",
    "draft-follow-ups",
    "draft-follow-up",
    "broaden-search",
    "prepare-interview",
    "mock-interview",
    "debrief-interview",
    "offer-questions",
    "prepare-negotiation",
    "draft-message",
    "research-company",
    "handle-requests",
    "review-search",
]

# Hitos de entrevista (fase 17): `upcoming`, programada y por empezar; `past`, ya empezada y no
# cancelada.
MilestoneRule = Literal["upcoming", "past"]


# Etapas en las que tiene sentido redactar el CV de una oferta (también para rehacerlo).
CV_STAGES = frozenset({Stage.APPROVED, Stage.CV_READY})
# Candidaturas enviadas y abiertas: a las que se escribe un seguimiento o un agradecimiento.
SENT_STAGES = frozenset({Stage.APPLIED, Stage.IN_PROCESS})
# Mensajes a personas de la empresa (fase 18): desde que apruebas la oferta.
OUTREACH_STAGES = frozenset({Stage.APPROVED, Stage.CV_READY, Stage.APPLIED, Stage.IN_PROCESS})
# Investigar la empresa: cualquier oferta abierta ya extraída (también para triarla).
RESEARCH_STAGES = OUTREACH_STAGES | {Stage.PENDING_TRIAGE}


@dataclass(frozen=True)
class Action:
    label: str
    prompt: str  # `{job_id}` si la acción es de una oferta; `{milestone_id}`, de un hito
    needs_job: bool = False
    stages: frozenset[Stage] = frozenset()  # con oferta: etapas en las que se puede lanzar
    wrong_stage: str = ""  # el motivo si la oferta no está en ellas
    milestone: MilestoneRule | None = None  # acción de un hito de entrevista (y de su oferta)
    needs_offer: bool = False  # solo si la oferta tiene un `offer_received`
    # Fase 19: herramientas MCP (sin prefijo) con las que se puede lanzar en segundo plano. Vacío:
    # la acción solo se abre en una terminal (pregunta, usa tu navegador o la web).
    background: tuple[str, ...] = ()
    skill: str | None = None  # el skill que usa la orden, si no se llama como la acción
    # Fase 24.5: los roles (`.agents/roles/`) en que delega el skill en segundo plano. Con techo
    # por configuración solo se pueden lanzar esos, y solo si sus herramientas caben en
    # `background` (`agent_run_config`).
    roles: tuple[str, ...] = ()


ACTIONS: dict[ActionId, Action] = {
    "search-jobs": Action(
        "Buscar ofertas",
        "Usa el skill search-jobs de CandidatAI para buscar ofertas en las plataformas activas.",
    ),
    # Las tres que admiten segundo plano (fase 19). Cada lista es lo mínimo que usan el skill y
    # sus roles: con un comodín, una oferta con una inyección podría llamar a herramientas que
    # escriben (`add_event`, `save_source`…).
    "process-jobs": Action(
        "Procesar ofertas",
        "Usa el skill process-jobs de CandidatAI con las ofertas pendientes de extraer.",
        background=("get_status", "list_jobs", "get_job", "save_extraction"),
        roles=("extractor",),
    ),
    "assess-fit": Action(
        "Evaluar encaje",
        "Usa el skill assess-fit de CandidatAI con las ofertas pendientes de revisar.",
        background=(
            "list_jobs",
            "get_profile",
            "get_context",
            "get_match",
            "get_extraction",
            "save_fit_assessment",
        ),
    ),
    "generate-cv": Action(
        "Generar CV",
        "Usa el skill generate-cv de CandidatAI para la oferta {job_id}.",
        needs_job=True,
        stages=CV_STAGES,
        wrong_stage="Solo se genera el CV de una oferta aprobada.",
        # Las obligatorias ausentes sin marcar se preguntan: `agent_runs` lo comprueba antes.
        background=(
            "list_jobs",
            "check_job_open",
            "get_match",
            "get_extraction",
            "get_profile",
            "get_context",
            "list_cv_templates",
            "save_cv_content",
            "get_cv_content",
            "save_cv_verification",
        ),
        roles=("writer", "verifier"),
    ),
    # Página «Skills» (fase 14). Los nombres de las skills salen de las ofertas, así que no van en
    # la orden: el agente los lee de las marcas con `get_skill_gaps`.
    "add-skills": Action(
        "Añadir al perfil las que tengo",
        "Usa el skill update-profile de CandidatAI para añadir a mi perfil las skills que he "
        "marcado como «La tengo» en la página Skills (get_skill_gaps con status have).",
    ),
    "training-plan": Action(
        "Plan de formación",
        "Usa el skill training-plan de CandidatAI con los huecos de skills que he marcado como "
        "«No la tengo».",
    ),
    # Inicio y «Respuestas» (fase 15): el agente propone; el usuario acepta en la UI.
    "review-replies": Action(
        "Revisar respuestas",
        "Usa el skill review-replies de CandidatAI con los correos de empresas sin clasificar.",
    ),
    # Procesos y ficha (fase 15): el agente redacta; el usuario copia y envía desde su correo.
    "draft-follow-ups": Action(
        "Redactar seguimientos",
        "Usa el skill draft-follow-up de CandidatAI con los seguimientos y agradecimientos "
        "pendientes.",
    ),
    # Plataformas (fase 16): títulos cercanos a los que apruebas. El agente propone; tú decides.
    "broaden-search": Action(
        "Ampliar búsqueda",
        "Usa el skill broaden-search de CandidatAI para proponerme títulos de puesto cercanos a "
        "los que apruebo.",
    ),
    # Embudo (fase 20): retrospectiva. Solo propone: los pesos y filtros los cambia el usuario.
    "review-search": Action(
        "Revisar mi búsqueda",
        "Usa el skill review-search de CandidatAI para hacer la retrospectiva de mi búsqueda: "
        "qué funciona y qué cambiar.",
    ),
    "draft-follow-up": Action(
        "Redactar seguimiento",
        "Usa el skill draft-follow-up de CandidatAI para la oferta {job_id}.",
        needs_job=True,
        stages=SENT_STAGES,
        wrong_stage="Solo se escribe a la empresa de una candidatura enviada y abierta.",
    ),
    # Ficha, hitos de entrevista (fase 17). El agente prepara, simula o repasa; lo que proponga
    # para el perfil pasa por `update-profile` y la confirmación del usuario.
    "prepare-interview": Action(
        "Preparar",
        "Usa el skill prepare-interview de CandidatAI para la entrevista {milestone_id} de la "
        "oferta {job_id}.",
        needs_job=True,
        milestone="upcoming",
    ),
    "mock-interview": Action(
        "Simulacro",
        "Usa el skill mock-interview de CandidatAI para la entrevista {milestone_id} de la "
        "oferta {job_id}.",
        needs_job=True,
        milestone="upcoming",
    ),
    "debrief-interview": Action(
        "Repasar",
        "Usa el skill debrief-interview de CandidatAI para repasar la entrevista {milestone_id} "
        "de la oferta {job_id}.",
        needs_job=True,
        milestone="past",
    ),
    # Ficha (fase 18): mensaje a una persona de la empresa y dosier de la empresa. El agente
    # redacta o investiga; la app no envía nada.
    "draft-message": Action(
        "Redactar mensaje",
        "Usa el skill draft-message de CandidatAI para la oferta {job_id}.",
        needs_job=True,
        stages=OUTREACH_STAGES,
        wrong_stage="Solo se escribe a la empresa de una oferta aprobada y abierta.",
    ),
    "research-company": Action(
        "Investigar empresa",
        "Usa el skill research-company de CandidatAI para la empresa de la oferta {job_id}.",
        needs_job=True,
        stages=RESEARCH_STAGES,
        wrong_stage="Solo para una oferta ya extraída y sin cerrar.",
    ),
    # Panel «Agente» (fase 19): la cola de encargos que dejaste para tu próxima sesión.
    "handle-requests": Action(
        "Atender encargos",
        "Usa el skill handle-requests de CandidatAI con los encargos pendientes.",
    ),
    "offer-questions": Action(
        "Dudas antes de aceptar",
        "Usa el skill debrief-interview de CandidatAI para revisar las dudas antes de aceptar la "
        "oferta {job_id}.",
        needs_job=True,
        stages=frozenset({Stage.IN_PROCESS}),
        wrong_stage="Solo con un proceso abierto.",
        needs_offer=True,
    ),
    # Fase 21: pregunta y admite pegar el contrato, así que solo en terminal.
    "prepare-negotiation": Action(
        "Preparar negociación",
        "Usa el skill prepare-negotiation de CandidatAI para la oferta {job_id}.",
        needs_job=True,
        stages=frozenset({Stage.IN_PROCESS}),
        wrong_stage="Solo con un proceso abierto.",
        needs_offer=True,
    ),
}
