from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.config import get_settings
from app.controllers.notificacion_controller import router as notificacion_router
from app.controllers.evento_controller import router as evento_router

settings = get_settings()

DESCRIPTION = """
## Microservicio de Notificaciones

Recibe eventos de los demás microservicios y genera notificaciones para los usuarios de **Emplea Humboldt**.

### Canales soportados
- **Email** vía AWS SES / SMTP
- **Push** vía Firebase Cloud Messaging (FCM)
- **In-app** almacenadas en base de datos

### Integración interna
Los microservicios publican eventos en `POST /api/v1/internal/eventos` usando el header `X-Internal-Key`.
Los tipos de evento soportados son:

| Origen | Tipo |
|--------|------|
| postulaciones | `cambio_estado_postulacion` |
| seguimiento | `practica_finalizada` |
| seguimiento | `vencimiento_proximo` |
| seguimiento | `evaluacion_pendiente` |
| seguimiento | `informe_pendiente` |
| autenticacion | `bienvenida` |
"""

TAGS_METADATA = [
    {
        "name": "Notificaciones",
        "description": "Consulta, marcado de leídas y métricas de notificaciones del usuario autenticado.",
    },
    {
        "name": "Eventos Internos",
        "description": "Endpoint privado para que otros microservicios publiquen eventos. Requiere header `X-Internal-Key`.",
    },
    {
        "name": "Health",
        "description": "Verificación del estado del servicio.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # El esquema de la BD lo gestiona Alembic (entrypoint.sh -> alembic upgrade head), no create_all.
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=DESCRIPTION,
    openapi_tags=TAGS_METADATA,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    root_path="/notificaciones",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notificacion_router, prefix="/api/v1")
app.include_router(evento_router, prefix="/api/v1/internal")


@app.get("/health", tags=["Health"], summary="Estado del servicio")
async def health_check():
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        tags=TAGS_METADATA,
        routes=app.routes,
    )
    schema.setdefault("components", {})["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Token JWT obtenido en el microservicio de autenticación.",
        },
        "InternalKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Internal-Key",
            "description": "Clave interna para comunicación entre microservicios.",
        },
    }
    schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
