from __future__ import annotations

import uuid
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, Enum, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Canal(str, enum.Enum):
    email = "email"
    push = "push"
    in_app = "in_app"


class TipoNotificacion(str, enum.Enum):
    # Postulaciones
    cambio_estado_postulacion = "cambio_estado_postulacion"
    postulacion_recibida = "postulacion_recibida"
    postulacion_aceptada = "postulacion_aceptada"
    postulacion_rechazada = "postulacion_rechazada"
    postulacion_en_revision = "postulacion_en_revision"
    postulacion_entrevista = "postulacion_entrevista"
    # Prácticas
    practica_iniciada = "practica_iniciada"
    practica_finalizada = "practica_finalizada"
    practica_suspendida = "practica_suspendida"
    vencimiento_proximo = "vencimiento_proximo"
    evaluacion_pendiente = "evaluacion_pendiente"
    informe_pendiente = "informe_pendiente"
    informe_aprobado = "informe_aprobado"
    # Vacantes
    nueva_vacante_matching = "nueva_vacante_matching"
    vacante_cerrada = "vacante_cerrada"
    # Sistema
    bienvenida = "bienvenida"
    sistema = "sistema"


class EstadoEnvio(str, enum.Enum):
    pendiente = "pendiente"
    enviado = "enviado"
    fallido = "fallido"
    omitido = "omitido"  # canal deshabilitado


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    tipo: Mapped[TipoNotificacion] = mapped_column(
        Enum(TipoNotificacion, name="tipo_notificacion_enum"), nullable=False, index=True
    )
    canal: Mapped[Canal] = mapped_column(
        Enum(Canal, name="canal_enum"), nullable=False
    )
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)

    leida: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    leida_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    estado_envio: Mapped[EstadoEnvio] = mapped_column(
        Enum(EstadoEnvio, name="estado_envio_enum"),
        default=EstadoEnvio.pendiente,
        nullable=False,
    )
    error_envio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Datos extra del evento origen (vacante_id, postulacion_id, etc.)
    datos_extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class EventoNotificacion(Base):
    """
    Registro de todos los eventos recibidos desde otros microservicios.
    Permite reintentar el procesamiento si falla el dispatch.
    """
    __tablename__ = "eventos_notificacion"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    origen_servicio: Mapped[str] = mapped_column(String(50), nullable=False)  # "postulaciones"|"seguimiento"|...
    tipo_evento: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    procesado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    intentos: Mapped[int] = mapped_column(default=0, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    procesado_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
