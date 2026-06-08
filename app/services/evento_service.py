from __future__ import annotations

import logging
import uuid
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notificacion import Canal, TipoNotificacion
from app.repositories.notificacion_repository import EventoRepository
from app.schemas.notificacion import EventoEntranteRequest
from app.services.notificacion_service import NotificacionService

logger = logging.getLogger(__name__)

# Canales por defecto para cada tipo de notificación
CANALES_POR_TIPO: dict = {
    TipoNotificacion.postulacion_recibida:       [Canal.in_app, Canal.email],
    TipoNotificacion.postulacion_aceptada:       [Canal.in_app, Canal.email, Canal.push],
    TipoNotificacion.postulacion_rechazada:      [Canal.in_app, Canal.email],
    TipoNotificacion.postulacion_en_revision:    [Canal.in_app],
    TipoNotificacion.postulacion_entrevista:     [Canal.in_app, Canal.email, Canal.push],
    TipoNotificacion.cambio_estado_postulacion:  [Canal.in_app],
    TipoNotificacion.practica_iniciada:          [Canal.in_app, Canal.email],
    TipoNotificacion.practica_finalizada:        [Canal.in_app, Canal.email],
    TipoNotificacion.practica_suspendida:        [Canal.in_app, Canal.email],
    TipoNotificacion.vencimiento_proximo:        [Canal.in_app, Canal.push],
    TipoNotificacion.evaluacion_pendiente:       [Canal.in_app, Canal.push],
    TipoNotificacion.informe_pendiente:          [Canal.in_app, Canal.push],
    TipoNotificacion.informe_aprobado:           [Canal.in_app],
    TipoNotificacion.nueva_vacante_matching:     [Canal.in_app],
    TipoNotificacion.bienvenida:                 [Canal.in_app, Canal.email],
}

# Mapeo: (origen_servicio, tipo_evento) → función procesadora
PROCESADORES: dict = {}


def procesador(origen: str, tipo: str):
    """Decorador para registrar procesadores de eventos."""
    def decorator(fn):
        PROCESADORES[(origen, tipo)] = fn
        return fn
    return decorator


@procesador("postulaciones", "cambio_estado_postulacion")
async def _procesar_cambio_estado_postulacion(
    payload: dict, noti_service: NotificacionService
) -> int:
    estado_nuevo = payload.get("estado_nuevo", "")
    estudiante_id = uuid.UUID(payload["estudiante_id"])
    empresa_id = uuid.UUID(payload["empresa_id"])
    postulacion_id = payload.get("postulacion_id")
    datos_extra = {"postulacion_id": postulacion_id, "vacante_id": payload.get("vacante_id")}

    tipo_map = {
        "aceptado":     TipoNotificacion.postulacion_aceptada,
        "rechazado":    TipoNotificacion.postulacion_rechazada,
        "en_revision":  TipoNotificacion.postulacion_en_revision,
        "entrevista":   TipoNotificacion.postulacion_entrevista,
    }
    tipo_estudiante = tipo_map.get(estado_nuevo, TipoNotificacion.cambio_estado_postulacion)

    mensajes_estudiante = {
        "aceptado":    "¡Tu postulación fue aceptada! Pronto recibirás más detalles de la empresa.",
        "rechazado":   "Tu postulación no fue seleccionada en esta ocasión. ¡Sigue intentando!",
        "en_revision": "La empresa está revisando tu postulación.",
        "entrevista":  "La empresa quiere conocerte. Prepárate para la entrevista.",
    }
    msg_estudiante = mensajes_estudiante.get(
        estado_nuevo, f"Tu postulación cambió al estado: {estado_nuevo}"
    )

    generadas = 0
    # Notificar al estudiante
    nots = await noti_service.crear_y_despachar(
        usuario_id=estudiante_id,
        tipo=tipo_estudiante,
        mensaje=msg_estudiante,
        canales=CANALES_POR_TIPO.get(tipo_estudiante, [Canal.in_app]),
        datos_extra=datos_extra,
    )
    generadas += len(nots)

    # Notificar a la empresa cuando llega una nueva postulación (estado_anterior = None)
    if payload.get("estado_anterior") is None:
        nots_empresa = await noti_service.crear_y_despachar(
            usuario_id=empresa_id,
            tipo=TipoNotificacion.postulacion_recibida,
            mensaje="Has recibido una nueva postulación para tu vacante.",
            canales=CANALES_POR_TIPO[TipoNotificacion.postulacion_recibida],
            datos_extra=datos_extra,
        )
        generadas += len(nots_empresa)

    return generadas


@procesador("seguimiento", "practica_finalizada")
async def _procesar_practica_finalizada(
    payload: dict, noti_service: NotificacionService
) -> int:
    estudiante_id = uuid.UUID(payload["estudiante_id"])
    empresa_id = uuid.UUID(payload["empresa_id"])
    datos_extra = {"practica_id": payload.get("practica_id")}
    generadas = 0

    for uid, msg in [
        (estudiante_id, "Tu práctica profesional ha finalizado. ¡Felicitaciones por completar esta etapa!"),
        (empresa_id,   "La práctica profesional del estudiante ha finalizado."),
    ]:
        nots = await noti_service.crear_y_despachar(
            usuario_id=uid,
            tipo=TipoNotificacion.practica_finalizada,
            mensaje=msg,
            canales=CANALES_POR_TIPO[TipoNotificacion.practica_finalizada],
            datos_extra=datos_extra,
        )
        generadas += len(nots)
    return generadas


@procesador("seguimiento", "vencimiento_proximo")
async def _procesar_vencimiento(payload: dict, noti_service: NotificacionService) -> int:
    estudiante_id = uuid.UUID(payload["estudiante_id"])
    datos_extra = {"practica_id": payload.get("practica_id")}
    dias = payload.get("datos_adicionales", {}).get("dias_restantes", "pocos")
    nots = await noti_service.crear_y_despachar(
        usuario_id=estudiante_id,
        tipo=TipoNotificacion.vencimiento_proximo,
        mensaje=f"Tu práctica vence en {dias} días. Asegúrate de tener todos los documentos al día.",
        canales=CANALES_POR_TIPO[TipoNotificacion.vencimiento_proximo],
        datos_extra=datos_extra,
    )
    return len(nots)


@procesador("seguimiento", "evaluacion_pendiente")
async def _procesar_evaluacion_pendiente(payload: dict, noti_service: NotificacionService) -> int:
    empresa_id = uuid.UUID(payload["empresa_id"])
    datos_extra = {"practica_id": payload.get("practica_id")}
    nots = await noti_service.crear_y_despachar(
        usuario_id=empresa_id,
        tipo=TipoNotificacion.evaluacion_pendiente,
        mensaje="Tienes una evaluación de desempeño pendiente para el estudiante en práctica.",
        canales=CANALES_POR_TIPO[TipoNotificacion.evaluacion_pendiente],
        datos_extra=datos_extra,
    )
    return len(nots)


@procesador("seguimiento", "informe_pendiente")
async def _procesar_informe_pendiente(payload: dict, noti_service: NotificacionService) -> int:
    estudiante_id = uuid.UUID(payload["estudiante_id"])
    datos_extra = {"practica_id": payload.get("practica_id")}
    nots = await noti_service.crear_y_despachar(
        usuario_id=estudiante_id,
        tipo=TipoNotificacion.informe_pendiente,
        mensaje="Debes entregar tu informe periódico de práctica.",
        canales=CANALES_POR_TIPO[TipoNotificacion.informe_pendiente],
        datos_extra=datos_extra,
    )
    return len(nots)


@procesador("autenticacion", "bienvenida")
async def _procesar_bienvenida(payload: dict, noti_service: NotificacionService) -> int:
    usuario_id = uuid.UUID(payload["usuario_id"])
    nombre = payload.get("nombres", "usuario")
    nots = await noti_service.crear_y_despachar(
        usuario_id=usuario_id,
        tipo=TipoNotificacion.bienvenida,
        mensaje=f"¡Hola {nombre}! Bienvenido a Emplea Humboldt. Completa tu perfil para encontrar las mejores oportunidades.",
        canales=CANALES_POR_TIPO[TipoNotificacion.bienvenida],
    )
    return len(nots)


class EventoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.evento_repo = EventoRepository(db)
        self.noti_service = NotificacionService(db)

    async def procesar_evento(self, request: EventoEntranteRequest) -> tuple[uuid.UUID, int]:
        evento = await self.evento_repo.crear(
            origen_servicio=request.origen_servicio,
            tipo_evento=request.tipo_evento,
            payload=request.payload,
        )

        clave = (request.origen_servicio, request.tipo_evento)
        procesador_fn = PROCESADORES.get(clave)

        if not procesador_fn:
            logger.warning("Sin procesador para evento: %s/%s", request.origen_servicio, request.tipo_evento)
            await self.evento_repo.marcar_procesado(evento)
            return evento.id, 0

        try:
            generadas = await procesador_fn(request.payload, self.noti_service)
            await self.evento_repo.marcar_procesado(evento)
            return evento.id, generadas
        except Exception as e:
            await self.evento_repo.marcar_fallido(evento, str(e))
            logger.error("Error procesando evento %s: %s", evento.id, str(e))
            raise
