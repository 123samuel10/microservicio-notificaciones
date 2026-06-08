from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload

from app.models.notificacion import (
    Notificacion,
    EventoNotificacion,
    Canal,
    TipoNotificacion,
    EstadoEnvio,
)


class NotificacionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def crear(
        self,
        usuario_id: uuid.UUID,
        tipo: TipoNotificacion,
        canal: Canal,
        titulo: str,
        mensaje: str,
        datos_extra: Optional[dict] = None,
    ) -> Notificacion:
        n = Notificacion(
            usuario_id=usuario_id,
            tipo=tipo,
            canal=canal,
            titulo=titulo,
            mensaje=mensaje,
            datos_extra=datos_extra,
        )
        self.db.add(n)
        await self.db.flush()
        await self.db.refresh(n)
        return n

    async def listar_por_usuario(
        self,
        usuario_id: uuid.UUID,
        solo_no_leidas: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notificacion]:
        query = (
            select(Notificacion)
            .where(
                Notificacion.usuario_id == usuario_id,
                Notificacion.canal == Canal.in_app,
            )
            .order_by(Notificacion.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if solo_no_leidas:
            query = query.where(Notificacion.leida == False)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def marcar_leidas(self, ids: List[uuid.UUID], usuario_id: uuid.UUID) -> int:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            update(Notificacion)
            .where(
                Notificacion.id.in_(ids),
                Notificacion.usuario_id == usuario_id,
                Notificacion.leida == False,
            )
            .values(leida=True, leida_at=now)
        )
        await self.db.flush()
        return result.rowcount

    async def marcar_todas_leidas(self, usuario_id: uuid.UUID) -> int:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            update(Notificacion)
            .where(
                Notificacion.usuario_id == usuario_id,
                Notificacion.canal == Canal.in_app,
                Notificacion.leida == False,
            )
            .values(leida=True, leida_at=now)
        )
        await self.db.flush()
        return result.rowcount

    async def actualizar_estado_envio(
        self, notificacion_id: uuid.UUID, estado: EstadoEnvio, error: Optional[str] = None
    ) -> None:
        await self.db.execute(
            update(Notificacion)
            .where(Notificacion.id == notificacion_id)
            .values(estado_envio=estado, error_envio=error)
        )
        await self.db.flush()

    async def contar_no_leidas(self, usuario_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count(Notificacion.id)).where(
                Notificacion.usuario_id == usuario_id,
                Notificacion.canal == Canal.in_app,
                Notificacion.leida == False,
            )
        )
        return result.scalar_one()

    # --- Métricas ---

    async def contar_total(self) -> int:
        result = await self.db.execute(select(func.count(Notificacion.id)))
        return result.scalar_one()

    async def contar_leidas(self) -> int:
        result = await self.db.execute(
            select(func.count(Notificacion.id)).where(Notificacion.leida == True)
        )
        return result.scalar_one()

    async def contar_por_campo(self, campo) -> dict:
        result = await self.db.execute(
            select(campo, func.count(Notificacion.id)).group_by(campo)
        )
        return {str(row[0]): row[1] for row in result.all()}

    async def tasa_apertura_por_canal(self) -> dict:
        result = await self.db.execute(
            select(
                Notificacion.canal,
                func.count(Notificacion.id).label("total"),
                func.sum(func.cast(Notificacion.leida, func.count(Notificacion.id).type)).label("leidas"),
            ).group_by(Notificacion.canal)
        )
        tasas = {}
        for row in result.all():
            canal, total, leidas = str(row[0]), row[1], row[2] or 0
            tasas[canal] = round(leidas / total, 4) if total else 0.0
        return tasas


class EventoRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def crear(
        self, origen_servicio: str, tipo_evento: str, payload: dict
    ) -> EventoNotificacion:
        ev = EventoNotificacion(
            origen_servicio=origen_servicio,
            tipo_evento=tipo_evento,
            payload=payload,
        )
        self.db.add(ev)
        await self.db.flush()
        await self.db.refresh(ev)
        return ev

    async def marcar_procesado(self, evento: EventoNotificacion) -> None:
        evento.procesado = True
        evento.procesado_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def marcar_fallido(self, evento: EventoNotificacion, error: str) -> None:
        evento.intentos += 1
        evento.error = error
        await self.db.flush()

    async def listar_pendientes(self, limit: int = 50) -> List[EventoNotificacion]:
        result = await self.db.execute(
            select(EventoNotificacion)
            .where(EventoNotificacion.procesado == False, EventoNotificacion.intentos < 3)
            .order_by(EventoNotificacion.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())
