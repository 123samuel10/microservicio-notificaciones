from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.deps import verify_internal_key
from app.database import get_db
from app.schemas.notificacion import EventoEntranteRequest, EventoEntranteResponse
from app.services.evento_service import EventoService

router = APIRouter(
    prefix="/eventos",
    tags=["Eventos Internos"],
    dependencies=[Depends(verify_internal_key)],
)


@router.post("/", response_model=EventoEntranteResponse, status_code=status.HTTP_202_ACCEPTED)
async def recibir_evento(
    request: EventoEntranteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint interno — llamado por otros microservicios para publicar eventos.
    Requiere cabecera: X-Internal-Key: <INTERNAL_API_KEY>

    Tipos de evento soportados:
    - postulaciones / cambio_estado_postulacion
    - seguimiento   / practica_finalizada
    - seguimiento   / vencimiento_proximo
    - seguimiento   / evaluacion_pendiente
    - seguimiento   / informe_pendiente
    - autenticacion / bienvenida
    """
    service = EventoService(db)
    evento_id, generadas = await service.procesar_evento(request)
    return EventoEntranteResponse(
        evento_id=evento_id,
        procesado=True,
        notificaciones_generadas=generadas,
        mensaje=f"Evento procesado. {generadas} notificación(es) generada(s).",
    )
