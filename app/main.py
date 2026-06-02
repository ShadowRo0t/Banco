import os
import time
import httpx
import logging
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from app.config import settings
from app.schemas import ClassificationRequest, ClassificationResponse, HealthResponse
from app.services import ClassifierService

# Configurar logs
logger = logging.getLogger("banco_api")
logging.basicConfig(level=logging.INFO)

# Inicializar FastAPI
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar Servicio de Clasificación
classifier_service = ClassifierService()

# ------------------------------------------------------------------------------
# Instrumentación de Métricas de Prometheus
# ------------------------------------------------------------------------------
# 1. Total de peticiones HTTP recibidas por la API
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total de peticiones HTTP procesadas por la API del banco",
    ["method", "endpoint", "status_code"]
)

# 2. Latencia total de las peticiones HTTP
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "Latencia total de peticiones HTTP en segundos",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, float("inf"))
)

# 3. Distribución de las prioridades y categorías detectadas
CLASSIFICATION_TOTAL = Counter(
    "classification_total",
    "Distribución de solicitudes bancarias por prioridad, categoría y método de resolución",
    ["prioridad", "categoria", "es_fallback"]
)

# 4. Latencia exclusiva de la inferencia del modelo
LLM_INFERENCE_DURATION_SECONDS = Histogram(
    "llm_inference_duration_seconds",
    "Latencia exclusiva de la inferencia del modelo Ollama local en segundos",
    ["prioridad", "modelo", "es_fallback"],
    buckets=(0.05, 0.1, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0, float("inf"))
)

# ------------------------------------------------------------------------------
# Middleware para medir latencias HTTP globales y contar peticiones
# ------------------------------------------------------------------------------
@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    start_time = time.perf_counter()
    endpoint = request.url.path
    method = request.method
    
    # Ignorar endpoints de monitoreo en las métricas de tráfico comercial para no sesgar
    is_monitor = endpoint in ["/metrics", "/health", "/docs", "/openapi.json"]
    
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        
        if not is_monitor:
            duration = time.perf_counter() - start_time
            HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(duration)
            
        return response
    except Exception as e:
        status_code = "500"
        if not is_monitor:
            HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
        raise e

# ------------------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------------------

@app.get("/", include_in_schema=False, response_class=HTMLResponse)
async def root():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Banco API</h1><p>Frontend file index.html not found.</p>")

@app.post(
    "/classify", 
    response_model=ClassificationResponse,
    summary="Clasificar la urgencia de una solicitud",
    response_description="Esquema JSON estructurado con la clasificación detallada"
)
async def classify(request: ClassificationRequest):
    """
    Recibe el texto enviado por el cliente en un chat o la transcripción telefónica, 
    y retorna un objeto JSON validando el nivel de prioridad (ALTA, MEDIA, BAJA), 
    la categoría, la derivación y una propuesta de respuesta automática.
    """
    logger.info(f"Procesando solicitud de clasificación para el texto de longitud: {len(request.text)}")
    
    try:
        result = await classifier_service.classify_request(request)
        
        # Registrar métricas específicas de clasificación
        CLASSIFICATION_TOTAL.labels(
            prioridad=result.prioridad,
            categoria=result.categoria,
            es_fallback=str(result.es_fallback)
        ).inc()
        
        # Registrar latencia exclusiva del LLM
        inference_seconds = result.tiempo_procesamiento_ms / 1000.0
        LLM_INFERENCE_DURATION_SECONDS.labels(
            prioridad=result.prioridad,
            modelo=result.modelo_utilizado,
            es_fallback=str(result.es_fallback)
        ).observe(inference_seconds)

        # Monitorear umbral operacional de latencia en logs
        if result.tiempo_procesamiento_ms > settings.LATENCY_THRESHOLD_MS:
            logger.warning(
                f"[ALERTA DE RENDIMIENTO] Tiempo de procesamiento de {result.tiempo_procesamiento_ms:.2f}ms "
                f"supera el umbral de {settings.LATENCY_THRESHOLD_MS}ms. Prioridad: {result.prioridad}"
            )
            
        return result
        
    except Exception as e:
        logger.error(f"Error crítico en el endpoint de clasificación: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Error interno del servidor al procesar la clasificación bancaria."
        )

@app.get(
    "/health", 
    response_model=HealthResponse,
    summary="Liveness y Readiness Probe de la aplicación"
)
async def health():
    """
    Verifica la salud de la API y el estado de la comunicación con la instancia local de Ollama.
    """
    ollama_status = "disconnected"
    try:
        # Hacer una llamada rápida al endpoint de salud de Ollama
        async with httpx.AsyncClient() as client:
            response = await client.get(settings.OLLAMA_HOST, timeout=2.0)
            if response.status_code == 200:
                ollama_status = "connected"
    except Exception as e:
        logger.warning(f"No se pudo conectar a Ollama en la ruta {settings.OLLAMA_HOST}: {e}")

    return HealthResponse(
        status="ok",
        ollama_status=ollama_status,
        version=settings.API_VERSION
    )

@app.get("/metrics", summary="Endpoint de exportación para Prometheus")
def metrics():
    """
    Retorna todas las métricas de Prometheus instrumentadas en formato crudo para el recolector (Scrape).
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
