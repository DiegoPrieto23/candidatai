"""Rellenar el selector de fecha y hora del portal (`date-time-picker`) desde una E2E.

No es un `<input type="datetime-local">`, sino un botón que abre un calendario: se elige como lo
haría una persona (mes, día, horas y minutos, «Listo»).
"""

from playwright.sync_api import Locator, expect

from tests.e2e.harness import t

MAX_MONTHS = 24


def pick_datetime(trigger: Locator, value: str) -> None:
    """Elige `value` (`YYYY-MM-DDTHH:mm`, o solo `YYYY-MM-DD`) en el selector que abre `trigger`."""
    date, _, time = value.partition("T")
    trigger.click()
    picker = trigger.page.get_by_role(
        "dialog", name=t("common.picker.chooseDateTime" if time else "common.picker.chooseDate")
    )
    day = picker.locator(f'[data-day="{date}"]')
    for _ in range(MAX_MONTHS):
        if day.count():
            break
        # El día de en medio de la rejilla siempre es del mes que se ve.
        shown = picker.locator("[data-day]").nth(15).get_attribute("data-day") or ""
        earlier = date[:7] < shown[:7]
        picker.get_by_role(
            "button", name=t("common.picker.prevMonth" if earlier else "common.picker.nextMonth")
        ).click()
    day.click()
    if time:
        hour, minute = time.split(":")
        picker.get_by_label(t("common.picker.hour")).fill(hour)
        picker.get_by_label(t("common.picker.minute")).fill(minute)
        picker.get_by_role("button", name=t("common.picker.done")).click()
    expect(picker).to_be_hidden()
