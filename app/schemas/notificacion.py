from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel, Field

from app.models.notificacion import Canal, TipoNotificacion, EstadoEnvio


# --- Notificación al usuario ---

class NotificacionResponse(BaseModel):
    id: uuid.UUID
    usuario_id: uuid.UUID
    tipo: TipoNotificacion
    canal: Canal
    titulo: str
    mensaje: str
    leida: bool
    leida_at: Optional[datetime] = None
    estado_envio: EstadoEnvio
    datos_extra: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MarcarLeidaRequest(BaseModel):
    ids: List[uuid.UUID] = Field(min_length=1)


# --- Eventos entrantes desde otros microservicios ---

class EventoPostulacionPayload(BaseModel):
    postulacion_id: uuid.UUID
    vacante_id: uuid.UUID
    estudiante_id: uuid.UUID
    empresa_id: uuid.UUID
    estado_nuevo: str
    estado_anterior: Optional[str] = None
    motivo: Optional[str] = None


class EventoPracticaPayload(BaseModel):
    practica_id: uuid.UUID
    vacante_id: uuid.UUID
    estudiante_id: uuid.UUID
    empresa_id: uuid.UUID
    tipo_evento: str  # "practica_finalizada" | "vencimiento_proximo" | "evaluacion_pendiente" | ...
    datos_adicionales: Optional[dict] = None


class EventoVacantePayload(BaseModel):
    vacante_id: uuid.UUID
    empresa_id: uuid.UUID
    tipo_evento: str  # "nueva_vacante" | "vacante_cerrada"
    area_conocimiento: Optional[str] = None


class EventoEntranteRequest(BaseModel):
    origen_servicio: str = Field(max_length=50)
    tipo_evento: str = Field(max_length=100)
    payload: dict


class EventoEntranteResponse(BaseModel):
    evento_id: uuid.UUID
    procesado: bool
    notificaciones_generadas: int
    mensaje: str


# --- Métricas ---

class MetricasNotificaciones(BaseModel):
    total_enviadas: int
    total_leidas: int
    total_no_leidas: int
    tasa_apertura: float
    por_tipo: dict
    por_canal: dict
    por_estado_envio: dict
    canales_efectividad: dict  # canal → tasa de apertura
