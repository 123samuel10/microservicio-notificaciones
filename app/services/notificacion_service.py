from __future__ import annotations

import uuid
import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notificacion import Canal, TipoNotificacion, Notificacion
from app.repositories.notificacion_repository import NotificacionRepository
from app.schemas.notificacion import MetricasNotificaciones, NotificacionResponse
from app.services.canal_service import despachar

logger = logging.getLogger(__name__)


# Mapa de tipo de notificación → título por defecto
TITULOS: dict = {
    TipoNotificacion.cambio_estado_postulacion: "Tu postulación ha cambiado de estado",
    TipoNotificacion.postulacion_recibida:       "Nueva postulación recibida",
    TipoNotificacion.postulacion_aceptada:       "¡Felicitaciones! Tu postulación fue aceptada",
    TipoNotificacion.postulacion_rechazada:      "Tu postulación no fue seleccionada",
    TipoNotificacion.postulacion_en_revision:    "Tu postulación está en revisión",
    TipoNotificacion.postulacion_entrevista:     "¡Tienes una entrevista programada!",
    TipoNotificacion.practica_iniciada:          "Tu práctica profesional ha comenzado",
    TipoNotificacion.practica_finalizada:        "Tu práctica profesional ha finalizado",
    TipoNotificacion.practica_suspendida:        "Tu práctica fue suspendida",
    TipoNotificacion.vencimiento_proximo:        "Vencimiento próximo en tu práctica",
    TipoNotificacion.evaluacion_pendiente:       "Tienes una evaluación pendiente",
    TipoNotificacion.informe_pendiente:          "Debes entregar un informe periódico",
    TipoNotificacion.informe_aprobado:           "Tu informe fue aprobado",
    TipoNotificacion.nueva_vacante_matching:     "Nueva vacante que coincide con tu perfil",
    TipoNotificacion.vacante_cerrada:            "Una vacante de tu empresa fue cerrada",
    TipoNotificacion.bienvenida:                 "¡Bienvenido a Emplea Humboldt!",
    TipoNotificacion.sistema:                    "Notificación del sistema",
}


class NotificacionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = NotificacionRepository(db)

    async def crear_y_despachar(
        self,
        usuario_id: uuid.UUID,
        tipo: TipoNotificacion,
        mensaje: str,
        canales: List[Canal],
        datos_extra: Optional[dict] = None,
        titulo: Optional[str] = None,
        email_destino: Optional[str] = None,
        push_token: Optional[str] = None,
    ) -> List[Notificacion]:
        titulo_final = titulo or TITULOS.get(tipo, "Notificación")
        creadas = []

        for canal in canales:
            notificacion = await self.repo.crear(
                usuario_id=usuario_id,
                tipo=tipo,
                canal=canal,
                titulo=titulo_final,
                mensaje=mensaje,
                datos_extra=datos_extra,
            )
            estado = await despachar(
                canal=canal,
                usuario_id=str(usuario_id),
                titulo=titulo_final,
                mensaje=mensaje,
                email_destino=email_destino,
                push_token=push_token,
            )
            await self.repo.actualizar_estado_envio(notificacion.id, estado)
            notificacion.estado_envio = estado
            creadas.append(notificacion)

        return creadas

    async def listar_mis_notificaciones(
        self,
        usuario_id: uuid.UUID,
        solo_no_leidas: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> List[NotificacionResponse]:
        offset = (page - 1) * page_size
        notificaciones = await self.repo.listar_por_usuario(
            usuario_id, solo_no_leidas, page_size, offset
        )
        return [NotificacionResponse.model_validate(n) for n in notificaciones]

    async def contar_no_leidas(self, usuario_id: uuid.UUID) -> int:
        return await self.repo.contar_no_leidas(usuario_id)

    async def marcar_leidas(self, ids: List[uuid.UUID], usuario_id: uuid.UUID) -> int:
        return await self.repo.marcar_leidas(ids, usuario_id)

    async def marcar_todas_leidas(self, usuario_id: uuid.UUID) -> int:
        return await self.repo.marcar_todas_leidas(usuario_id)

    async def get_metricas(self) -> MetricasNotificaciones:
        total = await self.repo.contar_total()
        leidas = await self.repo.contar_leidas()
        no_leidas = total - leidas
        tasa = round(leidas / total, 4) if total else 0.0

        por_tipo = await self.repo.contar_por_campo(
            __import__("app.models.notificacion", fromlist=["Notificacion"]).Notificacion.tipo
        )
        por_canal = await self.repo.contar_por_campo(
            __import__("app.models.notificacion", fromlist=["Notificacion"]).Notificacion.canal
        )
        por_estado = await self.repo.contar_por_campo(
            __import__("app.models.notificacion", fromlist=["Notificacion"]).Notificacion.estado_envio
        )
        efectividad = await self.repo.tasa_apertura_por_canal()

        return MetricasNotificaciones(
            total_enviadas=total,
            total_leidas=leidas,
            total_no_leidas=no_leidas,
            tasa_apertura=tasa,
            por_tipo=por_tipo,
            por_canal=por_canal,
            por_estado_envio=por_estado,
            canales_efectividad=efectividad,
        )
