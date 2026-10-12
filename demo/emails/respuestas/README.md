# Respuestas de empresas de ejemplo (fase 15)

Correos **ficticios** (empresas, personas y dominios inventados; los dominios `.example` no
existen) para probar la lectura de respuestas y el skill `revisar-respuestas` sin datos reales.

| Fichero | Empresa | Qué es | Propuesta esperada |
|---|---|---|---|
| `01-entrevista.eml` | Brétema Analytics | Invitación a entrevista el jueves 8 a las 10:00 | `interview_scheduled` con hito, confianza alta |
| `02-rechazo.eml` | Lonxa Retail Tech (vía Greenhouse) | Descarte | `rejected` |
| `03-prueba.eml` | Néboa Data | Prueba técnica con plazo el 14 de octubre | `test_assigned` con hito de todo el día |
| `04-oferta.eml` | Rías Software | Propuesta de incorporación | `offer_received` |
| `05-inyeccion.eml` | Castro Labs | Acuse de recibo con texto oculto dirigido a una IA | `none` con `injection_suspected`; `risk_flags` al guardarlo |

Para probarlos sin IMAP: crea ofertas de esas empresas, márcalas como enviadas y copia los
`.eml` a `data/inbox/respuestas/`; luego `uv run --directory backend cai replies poll`. Solo se
guardan los correos posteriores al envío.
