"""Catálogo cerrado de acciones «en tu agente»: la orden de cada una, dónde se puede
lanzar y con qué herramientas en segundo plano. Lo usan `agent_launch`, `agent_runs`,
`agent_requests` y `agent_prefs` (fase 24.4), que lo importan de aquí para no depender unos de
otros.
"""

from dataclasses import dataclass
from typing import Literal

from app.services.pipeline import Stage
from app.services.ui_language import Lang

ActionId = Literal[
    "search-jobs",
    "configure-platforms",
    "process-jobs",
    "assess-fit",
    "assess-fit-job",
    "generate-cv",
    "correct-cv",
    "verify-cv",
    "generate-cover-letter",
    "add-skills",
    "training-plan",
    "review-replies",
    "draft-follow-ups",
    "draft-follow-up",
    "broaden-search",
    "prepare-interview",
    "correct-interview-guide",
    "mock-interview",
    "debrief-interview",
    "offer-questions",
    "prepare-negotiation",
    "draft-message",
    "research-company",
    "handle-requests",
    "review-search",
    "expand",
    "create-profile",
    "import-profile-from-cv",
    "improve-profile-item",
    "translate-summary",
    "propose-stories",
    "import-cv-template",
    "assistant",
]

# Hitos de entrevista (fase 17): `upcoming`, programada y por empezar; `past`, ya empezada y no
# cancelada; `guide`, con guía ya hecha y cambios pedidos, también tras la entrevista.
MilestoneRule = Literal["upcoming", "past", "guide"]


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
    needs_cv: bool = False  # solo si la oferta ya tiene CV
    # Solo con una corrección pendiente: la orden no lleva su texto, lo lee el skill.
    needs_correction: bool = False
    # Fase 19: herramientas MCP (sin prefijo) con las que se puede lanzar en segundo plano. Vacío:
    # la acción solo se abre en una terminal (pregunta, usa tu navegador o la web).
    background: tuple[str, ...] = ()
    skill: str | None = None  # el skill que usa la orden, si no se llama como la acción
    # Fase 24.5: los roles (`.agents/roles/`) en que delega el skill en segundo plano. Con techo
    # por configuración solo se pueden lanzar esos, y solo si sus herramientas caben en
    # `background` (`agent_run_config`).
    roles: tuple[str, ...] = ()
    # Fase 25.7b: acción de un logro o una historia del perfil; la orden lleva su id
    # (`{profile_item}`), validado contra el perfil vigente antes de lanzar.
    profile_item: bool = False
    # Plantillas: convertir en plantilla un CV subido; la orden lleva su ruta (`{upload}`,
    # `data/uploads/<nombre>`), validada contra los ficheros subidos antes de lanzar.
    upload: bool = False
    # «Buscar ofertas»: admite elegir plataformas y una búsqueda puntual (`SearchScope`).
    search_scope: bool = False
    # «Asistente»: la orden lleva el id de una petición (`{assistant_id}`); su texto se
    # queda en la base de datos y lo lee el skill.
    assistant: bool = False
    # Sigue existiendo (ejecuciones antiguas, preferencias guardadas), pero la UI no la ofrece: ni
    # botón, ni fila en «Agente», ni en los niveles de gasto.
    hidden: bool = False


# Lo que lee el asistente del portal: datos que la app ya guarda estructurados.
ASSISTANT_READS: tuple[str, ...] = (
    "get_status",
    "get_schema",
    "list_jobs",
    "get_extraction",
    "get_match",
    "get_timeline",
    "get_search_titles",
    "get_profile",
    "get_context",
    "list_cv_templates",
    "get_cv_content",
    "get_cv_brief",
    "get_cv_correction",
    "get_cover_letter",
    "get_application_answers",
    "list_sources",
    "list_mail_sources",
    "list_followups_due",
    "list_upcoming",
    "get_funnel_stats",
    "get_calibration",
    "get_skill_gaps",
    "list_replies",
    "get_job_contacts",
    "get_company_research",
    "get_received_offer",
    "get_interviews",
    "get_interview_guide",
    "list_agent_requests",
)
# Lo que escribe, además de su respuesta: la valoración de una oferta y las indicaciones de una
# carta. Las dos se revisan después en la ficha y ninguna cambia de etapa una oferta.
ASSISTANT_WRITES: tuple[str, ...] = ("save_fit_assessment", "save_cover_letter_brief")


ACTIONS: dict[ActionId, Action] = {
    "search-jobs": Action(
        "Buscar ofertas",
        "Usa el skill search-jobs de CandidatAI para buscar ofertas en las plataformas activas.",
        search_scope=True,
    ),
    # «Dónde buscar»: el modo configurar del mismo skill. Pregunta dónde buscas y te recomienda
    # portales antes de guardar nada, así que solo en terminal.
    "configure-platforms": Action(
        "Configurar con mi agente",
        "Usa el skill search-jobs de CandidatAI en modo configurar: ayúdame a elegir en qué "
        "portales de empleo buscar y prepara sus búsquedas a partir de los puestos y las "
        "ubicaciones de mi perfil.",
        skill="search-jobs",
    ),
    # Las tres que admiten segundo plano (fase 19). Cada lista es lo mínimo que usan el skill y
    # sus roles: con un comodín, una oferta con una inyección podría llamar a herramientas que
    # escriben (`add_event`, `save_source`…).
    # Un solo paso (fase 1: leer con el rol `extractor`; fase 2: valorar lo leído). La sesión no lee
    # el texto de ninguna oferta, pero ahora lleva también las herramientas de la valoración.
    "process-jobs": Action(
        "Valorar las ofertas nuevas",
        "Usa el skill process-jobs de CandidatAI: lee las ofertas pendientes de leer y valora "
        "cuáles encajan conmigo.",
        background=(
            "get_status",
            "list_jobs",
            "get_job",
            "save_extraction",
            "get_profile",
            "get_context",
            "get_match",
            "get_extraction",
            "save_fit_assessment",
        ),
        roles=("extractor",),
    ),
    # Solo la valoración, para las que ya están leídas y esperan en «Por revisar». «Valorar las
    # ofertas nuevas» ya la hace en su fase 2, así que ya no se ofrece como botón.
    "assess-fit": Action(
        "Valorar las que están por revisar",
        "Usa el skill assess-fit de CandidatAI con las ofertas pendientes de revisar.",
        background=(
            "list_jobs",
            "get_profile",
            "get_context",
            "get_match",
            "get_extraction",
            "save_fit_assessment",
        ),
        hidden=True,
    ),
    # La misma valoración para una sola oferta, desde su ficha: la UI solo la ofrece sin valoración
    # o con la valoración desfasada (con los mismos datos, repetirla solo gasta y varía al azar).
    "assess-fit-job": Action(
        "Valorar esta oferta",
        "Usa el skill assess-fit de CandidatAI para la oferta {job_id}. Si ya tiene una "
        "valoración, vuelve a valorarla.",
        needs_job=True,
        stages=RESEARCH_STAGES,
        wrong_stage="Solo se valora una oferta abierta.",
        background=(
            "get_profile",
            "get_context",
            "get_match",
            "get_extraction",
            "save_fit_assessment",
        ),
        skill="assess-fit",
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
            "get_cv_brief",
            "get_match",
            "get_extraction",
            "get_profile",
            "get_context",
            "list_cv_templates",
            "check_cv_fit",
            "save_cv_content",
            "get_cv_content",
            "save_cv_verification",
        ),
        roles=("writer", "verifier"),
    ),
    # Aplica lo que el usuario pidió en la ficha y lo verifica. Quien corrige es el propio skill.
    "correct-cv": Action(
        "Corregir CV",
        "Usa el skill correct-cv de CandidatAI para la oferta {job_id}.",
        needs_job=True,
        stages=CV_STAGES,
        wrong_stage="Solo se corrige el CV de una oferta aprobada.",
        needs_correction=True,
        background=(
            "get_cv_correction",
            "decline_cv_correction",
            "get_cv_content",
            "get_extraction",
            "get_profile",
            "get_context",
            "check_cv_fit",
            "save_cv_content",
            "save_cv_verification",
        ),
        roles=("verifier",),
    ),
    # Sobre todo tras editar a mano: esa versión queda sin verificar.
    "verify-cv": Action(
        "Verificar CV",
        "Usa el skill verify-cv de CandidatAI para la oferta {job_id}.",
        needs_job=True,
        stages=CV_STAGES,
        wrong_stage="Solo se verifica el CV de una oferta aprobada.",
        needs_cv=True,
        background=(
            "get_cv_content",
            "get_extraction",
            "get_profile",
            "get_context",
            "save_cv_verification",
        ),
        roles=("verifier",),
    ),
    # Sin indicaciones, el skill pregunta una vez qué destacar; en segundo plano sigue con las de
    # por defecto (su sección «En segundo plano»). La verificación la hace el rol `verifier`.
    "generate-cover-letter": Action(
        "Escribir carta",
        "Usa el skill generate-cover-letter de CandidatAI para la oferta {job_id}.",
        needs_job=True,
        stages=CV_STAGES,
        wrong_stage="Solo se escribe la carta de una oferta aprobada.",
        background=(
            "get_cover_letter",
            "save_cover_letter_brief",
            "get_extraction",
            "get_profile",
            "get_cv_content",
            "get_context",
            "save_cover_letter",
            "save_cover_letter_verification",
        ),
        roles=("verifier",),
    ),
    # Página «Skills» (fase 14). Los nombres de las skills salen de las ofertas, así que no van en
    # la orden: el agente los lee de las marcas con `get_skill_gaps`.
    "add-skills": Action(
        "Añadir al perfil las que tengo",
        "Usa el skill update-profile de CandidatAI para añadir a mi perfil las skills que he "
        "marcado como «La tengo» en la página «Habilidades por desarrollar» (get_skill_gaps con "
        "status have).",
    ),
    # Perfil (fase 25.2): revisa el perfil entero y, si hay enlaces públicos, propone lo que sale de
    # ellos; pregunta antes de escribir, así que solo en terminal. El id sigue siendo `expand`.
    "expand": Action(
        "Mejorar perfil",
        "Usa el skill expand de CandidatAI para revisar mi perfil entero y proponerme mejoras "
        "(logros más concretos, huecos, datos que faltan) y, con los enlaces públicos de mi "
        "perfil, proyectos, skills, logros y certificaciones.",
    ),
    # «Mi perfil» sin perfil: crearlo desde el CV que se sube ahí (`data/documentos/cv/`).
    # Pregunta lo que el CV no dice y antes de escribir, así que solo en terminal.
    "create-profile": Action(
        "Crear mi perfil desde mi CV",
        "Usa el skill update-profile de CandidatAI para crear mi perfil a partir del CV que he "
        "subido a data/documentos/cv/.",
        skill="update-profile",
    ),
    # «Mi perfil» con perfil: traer a él lo que falte de un CV subido. Pregunta antes de escribir,
    # así que solo en terminal.
    "import-profile-from-cv": Action(
        "Importar información desde un CV",
        "Usa el skill update-profile de CandidatAI para añadir a mi perfil lo que le falte según "
        "el CV que he subido a data/documentos/cv/ (experiencia, skills, logros, formación…). Ya "
        "tengo perfil: no cambies ni borres lo que hay sin preguntarme, y enséñame las "
        "diferencias antes de guardar.",
        skill="update-profile",
    ),
    # «Mi perfil» (fase 25.7b): mejorar un logro o una historia, o proponer historias. Preguntan
    # antes de escribir, así que solo en terminal; «Mejorar» lleva el id del elemento.
    "improve-profile-item": Action(
        "Mejorar con mi agente",
        "Usa el skill update-profile de CandidatAI en modo «Mejorar un elemento» con "
        "{profile_item} de mi perfil.",
        skill="update-profile",
        profile_item=True,
    ),
    # Plantillas (fase 08.3): pregunta y te deja comparar antes de cerrar; solo en terminal.
    "import-cv-template": Action(
        "Convertir en plantilla",
        "Usa el skill import-cv-template de CandidatAI para convertir en plantilla {upload}.",
        upload=True,
    ),
    # «Mi perfil» (fase 41.2): el resumen en inglés desde el español. El agente deja una propuesta y
    # no escribe en el perfil (la usa o la descarta el usuario), así que admite segundo plano.
    "translate-summary": Action(
        "Generar resumen en inglés",
        "Usa el skill update-profile de CandidatAI en modo «Resumen en inglés»: traduce el resumen "
        "en español de mi perfil y déjalo como propuesta.",
        skill="update-profile",
        background=("get_profile", "save_profile_suggestion"),
    ),
    "propose-stories": Action(
        "Proponer historias desde mi experiencia",
        "Usa el skill update-profile de CandidatAI en modo «Proponer historias desde mi "
        "experiencia».",
        skill="update-profile",
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
    # Resultados (fase 20): retrospectiva. Solo propone: los pesos y filtros los cambia el usuario.
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
    # Aplica lo que el usuario pidió en la ficha, sin rehacer la guía. La orden no lleva su texto.
    "correct-interview-guide": Action(
        "Cambiar guía",
        "Usa el skill correct-interview-guide de CandidatAI para la entrevista {milestone_id} de "
        "la oferta {job_id}.",
        needs_job=True,
        milestone="guide",
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
    # «Asistente», en la ayuda del portal. Lo que escribe el usuario no va en la orden.
    # En segundo plano lee datos ya estructurados y solo escribe lo que ya escribe alguna otra
    # acción en segundo plano (`ASSISTANT_WRITES`). No lee texto crudo de ofertas ni de correos
    # (`get_job`, `get_reply`, `check_job_open`): es una sesión que escribe y que nadie mira. Sin
    # roles: lo que los necesita (un CV, una carta) se hace con su botón.
    "assistant": Action(
        "Asistente",
        "Usa el skill assistant de CandidatAI para la petición {assistant_id}.",
        assistant=True,
        background=(
            "get_assistant_request",
            "save_assistant_answer",
            "ask_user",
            "wait_user_action",
            *ASSISTANT_READS,
            *ASSISTANT_WRITES,
        ),
    ),
}


# --- La orden en inglés (fase 47.3) -----------------------------------------------------------
# Con el portal en inglés, la orden y el título de la ventana van en inglés y piden contestar en
# inglés. Los mismos marcadores que en español (un test lo comprueba). El CV y la carta siguen el
# idioma de la oferta: lo dice cada skill.
ENGLISH: dict[ActionId, tuple[str, str]] = {
    "search-jobs": (
        "Search for jobs",
        "Use the CandidatAI search-jobs skill to search for jobs on the active platforms.",
    ),
    "configure-platforms": (
        "Set up with my agent",
        "Use the CandidatAI search-jobs skill in configure mode: help me choose which job boards "
        "to search and prepare their searches from the roles and locations in my profile.",
    ),
    "process-jobs": (
        "Assess the new jobs",
        "Use the CandidatAI process-jobs skill: read the jobs waiting to be read and assess which "
        "ones fit me.",
    ),
    "assess-fit": (
        "Assess the ones to review",
        "Use the CandidatAI assess-fit skill with the jobs waiting for review.",
    ),
    "assess-fit-job": (
        "Assess this job",
        "Use the CandidatAI assess-fit skill for job {job_id}. If it already has an assessment, "
        "assess it again.",
    ),
    "generate-cv": ("Generate CV", "Use the CandidatAI generate-cv skill for job {job_id}."),
    "correct-cv": ("Correct CV", "Use the CandidatAI correct-cv skill for job {job_id}."),
    "verify-cv": ("Verify CV", "Use the CandidatAI verify-cv skill for job {job_id}."),
    "generate-cover-letter": (
        "Write cover letter",
        "Use the CandidatAI generate-cover-letter skill for job {job_id}.",
    ),
    "add-skills": (
        "Add the ones I have to my profile",
        "Use the CandidatAI update-profile skill to add to my profile the skills I marked as "
        "“I have it” on the “Skills to develop” page (get_skill_gaps with status have).",
    ),
    "expand": (
        "Improve profile",
        "Use the CandidatAI expand skill to review my whole profile and suggest improvements "
        "(more concrete achievements, gaps, missing data) and, from the public links in my "
        "profile, projects, skills, achievements and certifications.",
    ),
    "create-profile": (
        "Create my profile from my CV",
        "Use the CandidatAI update-profile skill to create my profile from the CV I uploaded to "
        "data/documentos/cv/.",
    ),
    "import-profile-from-cv": (
        "Import information from a CV",
        "Use the CandidatAI update-profile skill to add to my profile whatever it is missing "
        "according to the CV I uploaded to data/documentos/cv/ (experience, skills, achievements, "
        "education…). I already have a profile: do not change or delete what is there without "
        "asking me, and show me the differences before saving.",
    ),
    "improve-profile-item": (
        "Improve with my agent",
        "Use the CandidatAI update-profile skill in “Improve an item” mode with {profile_item} "
        "from my profile.",
    ),
    "import-cv-template": (
        "Turn into a template",
        "Use the CandidatAI import-cv-template skill to turn {upload} into a template.",
    ),
    "translate-summary": (
        "Generate English summary",
        "Use the CandidatAI update-profile skill in “English summary” mode: translate the Spanish "
        "summary of my profile and leave it as a suggestion.",
    ),
    "propose-stories": (
        "Suggest stories from my experience",
        "Use the CandidatAI update-profile skill in “Suggest stories from my experience” mode.",
    ),
    "training-plan": (
        "Training plan",
        "Use the CandidatAI training-plan skill with the skill gaps I marked as “I don't have it”.",
    ),
    "review-replies": (
        "Review replies",
        "Use the CandidatAI review-replies skill with the unclassified emails from companies.",
    ),
    "draft-follow-ups": (
        "Draft follow-ups",
        "Use the CandidatAI draft-follow-up skill with the pending follow-ups and thank-you notes.",
    ),
    "broaden-search": (
        "Broaden search",
        "Use the CandidatAI broaden-search skill to suggest job titles close to the ones I "
        "approve.",
    ),
    "review-search": (
        "Review my search",
        "Use the CandidatAI review-search skill to run the retrospective of my search: what works "
        "and what to change.",
    ),
    "draft-follow-up": (
        "Draft follow-up",
        "Use the CandidatAI draft-follow-up skill for job {job_id}.",
    ),
    "prepare-interview": (
        "Prepare",
        "Use the CandidatAI prepare-interview skill for interview {milestone_id} of job {job_id}.",
    ),
    "correct-interview-guide": (
        "Change guide",
        "Use the CandidatAI correct-interview-guide skill for interview {milestone_id} of job "
        "{job_id}.",
    ),
    "mock-interview": (
        "Mock interview",
        "Use the CandidatAI mock-interview skill for interview {milestone_id} of job {job_id}.",
    ),
    "debrief-interview": (
        "Debrief",
        "Use the CandidatAI debrief-interview skill to debrief interview {milestone_id} of job "
        "{job_id}.",
    ),
    "draft-message": ("Draft message", "Use the CandidatAI draft-message skill for job {job_id}."),
    "research-company": (
        "Research company",
        "Use the CandidatAI research-company skill for the company of job {job_id}.",
    ),
    "handle-requests": (
        "Handle requests",
        "Use the CandidatAI handle-requests skill with the pending requests.",
    ),
    "offer-questions": (
        "Questions before accepting",
        "Use the CandidatAI debrief-interview skill to review the questions before accepting the "
        "offer for job {job_id}.",
    ),
    "prepare-negotiation": (
        "Prepare negotiation",
        "Use the CandidatAI prepare-negotiation skill for job {job_id}.",
    ),
    "assistant": (
        "Assistant",
        "Use the CandidatAI assistant skill for request {assistant_id}.",
    ),
}

# Al final de cada orden en inglés: así contesta en inglés aunque los skills estén en español.
ENGLISH_REPLY = (
    " Talk to me in English. Documents (CV, cover letter) keep the language of the job posting."
)


def label(action: ActionId, lang: Lang = "es") -> str:
    """El nombre de la acción en ese idioma (para el título de la ventana)."""
    return ENGLISH[action][0] if lang == "en" else ACTIONS[action].label


def prompt_template(action: ActionId, lang: Lang = "es") -> str:
    """La orden sin rellenar, en ese idioma."""
    return ENGLISH[action][1] if lang == "en" else ACTIONS[action].prompt
