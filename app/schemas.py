from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class ClassificationRequest(BaseModel):
    text: str = Field(
        ..., 
        min_length=5, 
        max_length=5000, 
        description="Texto del chat del cliente o transcripción de la llamada telefónica.",
        examples=["Hola, me acaban de robar la tarjeta de débito y veo cobros que no reconozco."]
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadata adicional sobre la interacción (ej. canal, cliente_id, etc.)"
    )

class ClassificationResponse(BaseModel):
    prioridad: str = Field(
        ..., 
        description="Nivel de urgencia de la solicitud: ALTA, MEDIA o BAJA."
    )
    categoria: str = Field(
        ..., 
        description="Categoría identificada (ej. Fraude / Robo, Problemas de Facturación, Consultas Generales)."
    )
    motivo: str = Field(
        ..., 
        description="Breve justificación de por qué se asignó esta prioridad y categoría."
    )
    derivar_a_humano: bool = Field(
        ..., 
        description="True si requiere atención inmediata por parte de un operador humano."
    )
    metodo_derivacion: str = Field(
        ..., 
        description="Destinatario o canal sugerido para la atención (ej. Operador de Emergencias, Soporte Comercial)."
    )
    respuesta_sugerida: str = Field(
        ..., 
        description="Plantilla de respuesta sugerida para el cliente antes de la intervención o auto-servicio."
    )
    tiempo_procesamiento_ms: float = Field(
        ..., 
        description="Tiempo total en milisegundos que tomó realizar la inferencia y validación."
    )
    modelo_utilizado: str = Field(
        ..., 
        description="Nombre del modelo que resolvió la solicitud."
    )
    es_fallback: bool = Field(
        ..., 
        description="Indica si la clasificación se generó mediante el mecanismo de contingencia heurística."
    )

class HealthResponse(BaseModel):
    status: str = Field(..., description="Estado del servicio FastAPI (ok).")
    ollama_status: str = Field(..., description="Estado de la conexión con Ollama (connected / disconnected).")
    version: str = Field(..., description="Versión actual de la aplicación.")
