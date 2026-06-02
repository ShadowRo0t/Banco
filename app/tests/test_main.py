import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app, classifier_service
from app.schemas import ClassificationResponse

client = TestClient(app)

def test_root_endpoint():
    """Prueba que el endpoint raíz responda correctamente sirviendo el HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Clasificación" in response.text

def test_health_endpoint():
    """Prueba el endpoint de salud de la API."""
    with patch("httpx.AsyncClient.get") as mock_get:
        # Simular que Ollama responde con éxito
        mock_get.return_value.status_code = 200
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["ollama_status"] == "connected"

def test_health_endpoint_ollama_disconnected():
    """Prueba el endpoint de salud de la API cuando Ollama está caído."""
    with patch("httpx.AsyncClient.get", side_effect=Exception("Conexión rechazada")):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["ollama_status"] == "disconnected"

def test_metrics_endpoint():
    """Prueba que el recolector de Prometheus reciba la estructura correcta de métricas."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "classification_total" in response.text

@pytest.mark.asyncio
async def test_classification_endpoint_success():
    """Prueba el endpoint de clasificación simulando una respuesta exitosa del LLM."""
    mock_response = ClassificationResponse(
        prioridad="ALTA",
        categoria="Fraude / Seguridad",
        motivo="Cliente reporta clonación activa de su tarjeta bancaria.",
        derivar_a_humano=True,
        metodo_derivacion="Operador de Emergencias",
        respuesta_sugerida="Lamentamos el inconveniente. Hemos bloqueado tu tarjeta inmediatamente.",
        tiempo_procesamiento_ms=150.0,
        modelo_utilizado="llama3.2:3b",
        es_fallback=False
    )
    
    with patch.object(classifier_service, "classify_request", AsyncMock(return_value=mock_response)):
        payload = {"text": "Me clonaron mi tarjeta de credito y me estan haciendo cargos extraños!"}
        response = client.post("/classify", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["prioridad"] == "ALTA"
        assert data["categoria"] == "Fraude / Seguridad"
        assert data["derivar_a_humano"] is True
        assert data["es_fallback"] is False
        assert data["modelo_utilizado"] == "llama3.2:3b"

def test_heuristic_fallback_high_priority():
    """Verifica directamente el motor heurístico de contingencia para alertas de alta prioridad (ALTA)."""
    text = "Auxilio! perdí mi tarjeta de crédito esta tarde y creo que me la robaron o me la van a clonar"
    response = classifier_service._heuristic_fallback(text, 1.5)
    
    assert response.prioridad == "ALTA"
    assert response.categoria == "Fraude / Seguridad"
    assert response.derivar_a_humano is True
    assert response.es_fallback is True
    assert "Fallback" in response.modelo_utilizado

def test_heuristic_fallback_medium_priority():
    """Verifica directamente el motor heurístico de contingencia para cobros comerciales (MEDIA)."""
    text = "Tengo un reclamo sobre mi última factura, me aplicaron un doble cobro y una comisión de más"
    response = classifier_service._heuristic_fallback(text, 1.5)
    
    assert response.prioridad == "MEDIA"
    assert response.categoria == "Facturación / Operaciones"
    assert response.derivar_a_humano is True
    assert response.es_fallback is True

def test_heuristic_fallback_low_priority():
    """Verifica directamente el motor heurístico de contingencia para consultas generales (BAJA)."""
    text = "Hola, ¿podrían decirme en qué horario atiende la sucursal del centro comercial?"
    response = classifier_service._heuristic_fallback(text, 1.5)
    
    assert response.prioridad == "BAJA"
    assert response.categoria == "Consultas Generales"
    assert response.derivar_a_humano is False
    assert response.es_fallback is True

def test_classification_payload_validation():
    """Prueba que el payload sea validado correctamente por la API."""
    # Enviar texto muy corto (menos del min_length de 5 caracteres)
    payload = {"text": "A"}
    response = client.post("/classify", json=payload)
    assert response.status_code == 422
