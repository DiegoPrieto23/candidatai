"""Avisos al usuario (captcha, login…): los que esperan respuesta y tu respuesta desde el pop-up.

Capa fina sobre `services/prompts.py`. Los crea el agente (`request_user_action`) o el worker en
una candidatura asistida; aquí solo se leen y se contestan.
"""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.api.deps import SessionDep
from app.services import prompts

router = APIRouter(prefix="/prompts", tags=["prompts"])


class AnswerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: prompts.Outcome  # `done` («Ya está») o `skipped` («Saltar»)


@router.get("/pending", operation_id="list_pending_prompts")
def list_pending_prompts(session: SessionDep) -> prompts.PendingPrompts:
    """Avisos que esperan tu respuesta, para el pop-up."""
    return prompts.list_pending(session)


@router.post("/{prompt_id}/answer", operation_id="answer_prompt")
def answer_prompt(session: SessionDep, prompt_id: int, body: AnswerBody) -> prompts.PromptView:
    """«Ya está» o «Saltar». En una candidatura asistida, «Ya está» vuelve a rellenar la página."""
    return prompts.answer(session, prompt_id, body.outcome)
