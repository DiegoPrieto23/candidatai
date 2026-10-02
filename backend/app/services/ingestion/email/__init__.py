"""Alertas de empleo por correo (fase 09b, `docs/FUENTES_OFERTAS.md` §Alertas por correo).

- `message.py`: de los bytes de un correo a lo que importa (remitente, fecha, HTML y texto);
- `parsers/`: de un correo a las ofertas que anuncia, con un parser por plataforma;
- `mailboxes.py`: lectura del buzón IMAP en solo lectura o de la carpeta `data/inbox/`;
- `service.py`: la pasada completa (deduplicación por `Message-ID`, alta y `source_runs`).

Todo el contenido de un correo es no confiable: se trata como datos y no se sigue ningún enlace
de LinkedIn.
"""
