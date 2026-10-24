# Fase 10 · Seguimiento y analítica

## Contexto
Lee `docs/DATA_MODEL.md` §Catálogo de eventos, `docs/AGENT_INTERFACE.md` (herramientas de la fase 10)
y los skills `preparar-candidatura`, `preparar-entrevista` y `resumen-diario`.

## Objetivo
No perder ningún proceso y saber qué funciona.

Se hace en tres subfases, en la rama `fase/10-seguimiento-analitica` y con un commit por subfase:
**10.1** seguimiento (kanban, ficha de proceso, hitos, seguimientos y calendario;
`dev/prompts/10.1-seguimiento.md`), **10.2** analítica (dashboard del embudo;
`dev/prompts/10.2-analitica.md`) y **10.3** paquete de candidatura (`dev/prompts/10.3-paquete-candidatura.md`).

## Alcance
1. **Kanban** en la UI, con columnas por etapa desde `approved` hasta `closed`. Arrastrar una
   tarjeta abre un diálogo que registra el evento correspondiente (fecha editable, nota).
   Nada cambia de columna sin evento.
2. **Ficha de proceso**: contactos, próximos hitos con fecha y hora (Europe/Madrid), notas y
   documentos usados.
3. **Seguimientos**: regla configurable (por defecto 10 días sin respuesta tras `applied`) →
   aviso en la UI y `list_followups_due` en la MCP.
4. **Calendario**: exportación `.ics` por evento y un feed `.ics` local de todos los hitos
   futuros, para suscribirse desde Google Calendar u Outlook.
5. **Dashboard del embudo**: conversión por etapa, por fuente, por tipo de puesto y por semana;
   tiempo medio hasta la primera respuesta; motivos de descarte más frecuentes. Consultas SQL en
   `app/services/analytics.py` con tests y gráficas con Recharts.
6. Interfaz para agentes (MCP y CLI): `save_application_answers`, `list_followups_due`, `list_upcoming` y `get_funnel_stats`.
7. UI de "Paquete de candidatura": CV elegido, respuestas de screening (editables) y la carta
   seleccionada si la hay (de la fase 08c: texto para copiar y PDF), con botón para copiar cada
   respuesta. La carta no se redacta aquí: `ApplicationAnswers` ya no lleva `cover_letter`.

## Fuera de alcance
Envío automático.

## Criterios de aceptación
- Tests de las consultas de analítica con un histórico de eventos sintético.
- El `.ics` se importa bien en Google Calendar (prueba manual).
- El dashboard carga en menos de 1 s con 1 000 ofertas sintéticas.

## Al terminar
Actualiza `dev/ROADMAP.md` y propón mensaje de commit.
