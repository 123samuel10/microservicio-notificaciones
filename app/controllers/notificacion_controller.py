from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.deps import UsuarioToken, get_current_user
from app.database import get_db
from app.schemas.notificacion import (
    MarcarLeidaRequest,
    MetricasNotificaciones,
    NotificacionResponse,
)
from app.services.notificacion_service import NotificacionService

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])


@router.get("", response_model=List[NotificacionResponse])
async def mis_notificaciones(
    solo_no_leidas: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(get_current_user),
):
    service = NotificacionService(db)
    return await service.listar_mis_notificaciones(
        usuario.id, solo_no_leidas, page, page_size
    )


@router.get("/no-leidas/count")
async def contar_no_leidas(
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(get_current_user),
):
    service = NotificacionService(db)
    count = await service.contar_no_leidas(usuario.id)
    return {"no_leidas": count}


@router.patch("/marcar-leidas", status_code=status.HTTP_200_OK)
async def marcar_leidas(
    datos: MarcarLeidaRequest,
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(get_current_user),
):
    service = NotificacionService(db)
    actualizadas = await service.marcar_leidas(datos.ids, usuario.id)
    return {"actualizadas": actualizadas}


@router.patch("/marcar-todas-leidas", status_code=status.HTTP_200_OK)
async def marcar_todas_leidas(
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(get_current_user),
):
    service = NotificacionService(db)
    actualizadas = await service.marcar_todas_leidas(usuario.id)
    return {"actualizadas": actualizadas}


@router.get("/metricas", response_model=MetricasNotificaciones)
async def metricas(
    db: AsyncSession = Depends(get_db),
    _: UsuarioToken = Depends(get_current_user),
):
    service = NotificacionService(db)
    return await service.get_metricas()
