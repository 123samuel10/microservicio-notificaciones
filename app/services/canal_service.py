from __future__ import annotations

import logging
from typing import Optional

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import get_settings
from app.models.notificacion import Canal, EstadoEnvio

logger = logging.getLogger(__name__)
settings = get_settings()


async def despachar(
    canal: Canal,
    usuario_id: str,
    titulo: str,
    mensaje: str,
    email_destino: Optional[str] = None,
    push_token: Optional[str] = None,
) -> EstadoEnvio:
    """
    Despacha la notificación por el canal indicado.
    Retorna el estado resultante del envío.
    """
    if canal == Canal.in_app:
        # in_app no requiere envío externo — ya queda persistida en la BD
        return EstadoEnvio.enviado

    if canal == Canal.email:
        return await _enviar_email(email_destino, titulo, mensaje)

    if canal == Canal.push:
        return await _enviar_push(push_token, titulo, mensaje)

    return EstadoEnvio.omitido


async def _enviar_email(destino: Optional[str], asunto: str, cuerpo: str) -> EstadoEnvio:
    if not settings.EMAIL_HABILITADO:
        logger.info("[EMAIL omitido — deshabilitado] Para: %s | Asunto: %s", destino, asunto)
        return EstadoEnvio.omitido

    if not destino:
        logger.warning("[EMAIL] Sin dirección de destino — omitiendo")
        return EstadoEnvio.omitido

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = destino
    msg.attach(MIMEText(cuerpo, "html", "utf-8"))

    try:
        async with aiosmtplib.SMTP(
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            start_tls=True,
        ) as smtp:
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            await smtp.send_message(msg)
        logger.info("[EMAIL enviado] Para: %s | Asunto: %s", destino, asunto)
        return EstadoEnvio.enviado
    except Exception as e:
        logger.error("[EMAIL fallido] Para: %s | Error: %s", destino, str(e))
        return EstadoEnvio.fallido


async def _enviar_push(token: Optional[str], titulo: str, cuerpo: str) -> EstadoEnvio:
    if not settings.PUSH_HABILITADO:
        logger.info("[PUSH omitido — deshabilitado] Titulo: %s", titulo)
        return EstadoEnvio.omitido

    if not token:
        logger.warning("[PUSH] Sin token de dispositivo — omitiendo")
        return EstadoEnvio.omitido

    # Integración FCM — requiere httpx y FCM_SERVER_KEY configurado
    import httpx
    payload = {
        "to": token,
        "notification": {"title": titulo, "body": cuerpo},
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                "https://fcm.googleapis.com/fcm/send",
                json=payload,
                headers={
                    "Authorization": f"key={settings.FCM_SERVER_KEY}",
                    "Content-Type": "application/json",
                },
            )
        if resp.status_code == 200:
            logger.info("[PUSH enviado] Token: %s", token[:10])
            return EstadoEnvio.enviado
        logger.error("[PUSH fallido] Status: %s", resp.status_code)
        return EstadoEnvio.fallido
    except Exception as e:
        logger.error("[PUSH fallido] Error: %s", str(e))
        return EstadoEnvio.fallido
