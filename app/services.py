import re
import json
import logging
import asyncio
import time
from typing import Dict, Any
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings
from app.schemas import ClassificationResponse, ClassificationRequest

logger = logging.getLogger("banco_classifier")
logging.basicConfig(level=logging.INFO)

class ClassifierService:
    def __init__(self):
        # Configurar la conexión con Ollama usando LangChain
        self.host = settings.OLLAMA_HOST
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.LLM_TIMEOUT_SECONDS
        
        logger.info(f"Inicializando ChatOllama conectado a {self.host} con el modelo {self.model}")
        try:
            self.llm = ChatOllama(
                base_url=self.host,
                model=self.model,
                temperature=0.0,  # Queremos respuestas deterministas y consistentes
                timeout=self.timeout
            )
        except Exception as e:
            logger.error(f"Error al inicializar ChatOllama: {e}. Se utilizará el fallback heurístico si Ollama no está disponible.")
            self.llm = None

    def _heuristic_fallback(self, text: str, processing_time_ms: float) -> ClassificationResponse:
        """
        Mecanismo de contingencia (fallback determinista) basado en reglas heurísticas y expresiones regulares.
        Garantiza que la API responda en menos de 5ms en caso de desconexión o falla del LLM local.
        """
        text_lower = text.lower()
        
        # Palabras clave críticas para prioridad ALTA
        high_priority_keywords = [
            r"clon", r"robo", r"robar", r"perdi", r"perder", r"extrav", r"fraude", r"estafa", 
            r"hacke", r"phishing", r"no reconozco", r"no reconocido", r"bloque", r"suplant",
            r"emergencia", r"seguridad", r"compras sospechosas", r"movimientos extraños"
        ]
        
        # Palabras clave comerciales/administrativas para prioridad MEDIA
        medium_priority_keywords = [
            r"factura", r"cobro", r"comision", r"tarifa", r"duplicado", r"doble", r"disputa", 
            r"aclaracion", r"renova", r"venci", r"login", r"ingreso", r"clave de internet",
            r"acceso", r"limite", r"transferencia", r"saldo incorrecto"
        ]

        # Comprobar prioridad ALTA
        for pattern in high_priority_keywords:
            if re.search(pattern, text_lower):
                return ClassificationResponse(
                    prioridad="ALTA",
                    categoria="Fraude / Seguridad",
                    motivo=f"Clasificación heurística preventiva activada por término clave de seguridad relacionado con '{pattern}'.",
                    derivar_a_humano=True,
                    metodo_derivacion="Operador de Emergencias / Prevención de Fraude",
                    respuesta_sugerida="Hemos detectado una situación crítica de seguridad en tu reporte. Un agente experto de nuestro equipo de contingencias se pondrá en contacto contigo inmediatamente. Por seguridad, te sugerimos no compartir contraseñas por este canal.",
                    tiempo_procesamiento_ms=processing_time_ms,
                    modelo_utilizado="Motor Heurístico de Fallback (Regex-v1)",
                    es_fallback=True
                )

        # Comprobar prioridad MEDIA
        for pattern in medium_priority_keywords:
            if re.search(pattern, text_lower):
                return ClassificationResponse(
                    prioridad="MEDIA",
                    categoria="Facturación / Operaciones",
                    motivo=f"Clasificación heurística activada por coincidencia comercial o de facturación relacionada con '{pattern}'.",
                    derivar_a_humano=True,
                    metodo_derivacion="Soporte Comercial / Ejecutivo de Cuentas",
                    respuesta_sugerida="Hemos recibido tu solicitud relacionada con temas comerciales o de facturación. Un ejecutivo revisará tu caso en un plazo no mayor a 2 horas hábiles.",
                    tiempo_procesamiento_ms=processing_time_ms,
                    modelo_utilizado="Motor Heurístico de Fallback (Regex-v1)",
                    es_fallback=True
                )

        # Por defecto, prioridad BAJA
        return ClassificationResponse(
            prioridad="BAJA",
            categoria="Consultas Generales",
            motivo="Clasificación heurística por defecto: no se identificaron términos críticos ni operativos urgentes.",
            derivar_a_humano=False,
            metodo_derivacion="Auto-servicio",
            respuesta_sugerida="Gracias por comunicarte con nosotros. Tu consulta ha sido asignada a nuestra cola de atención general. También puedes consultar tus dudas en nuestra sección de Preguntas Frecuentes en la App del Banco.",
            tiempo_procesamiento_ms=processing_time_ms,
            modelo_utilizado="Motor Heurístico de Fallback (Regex-v1)",
            es_fallback=True
        )

    def _extract_json_block(self, text: str) -> Dict[str, Any]:
        """
        Limpia y extrae un bloque JSON del texto retornado por el LLM en caso de que
        haya incluido markdown o texto explicativo (ej. ```json ... ```).
        """
        # Buscar bloques JSON markdown
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1).strip())
            
        # Si no tiene markdown pero tiene llaves
        match = re.search(r"(\{.*?\})", text, re.DOTALL)
        if match:
            return json.loads(match.group(1).strip())
            
        # Intentar cargar directo si es json limpio
        return json.loads(text.strip())

    async def classify_request(self, request: ClassificationRequest) -> ClassificationResponse:
        start_time = time.perf_counter()
        
        # Si ChatOllama no se inicializó correctamente
        if not self.llm:
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            logger.warning("Instancia de ChatOllama no disponible. Usando fallback heurístico inmediato.")
            return self._heuristic_fallback(request.text, processing_time_ms)

        system_prompt = """
        Eres un asistente de inteligencia artificial experto en seguridad bancaria y servicio al cliente de un banco principal.
        Tu trabajo es analizar la solicitud del cliente (que puede venir de chat o transcripciones de llamadas) y clasificarla de forma precisa y estructurada en formato JSON en español.

        Reglas de clasificación de PRIORIDAD:
        - ALTA: Solicitudes críticas de emergencia que representan riesgo financiero inmediato, seguridad comprometida o fraude. Ejemplos: clonación de tarjetas, transacciones no reconocidas, robo de credenciales, pérdida de tarjeta, phishing, hackeo de cuenta bancaria.
        - MEDIA: Problemas financieros no urgentes, errores de facturación, cobros duplicados, comisiones mal aplicadas, problemas de acceso a canales digitales, dudas sobre transferencias no ejecutadas.
        - BAJA: Consultas generales, horarios de sucursales, ubicaciones, estado de puntos de fidelidad, información de requisitos sobre préstamos, tasas informativas.

        Categorías recomendadas:
        - "Fraude / Seguridad" (para robos, clonaciones, compras sospechosas)
        - "Facturación / Cobros" (para cobros indebidos, comisiones, disputas)
        - "Operaciones / Cuentas" (problemas con transferencias, renovación de tarjetas)
        - "Consultas Generales" (horarios, sucursales, puntos de fidelidad)

        Debes responder ÚNICAMENTE con un objeto JSON válido y estructurado, sin introducciones ni comentarios explicativos de ningún tipo.
        El JSON debe seguir exactamente el siguiente esquema:
        {{
          "prioridad": "ALTA" | "MEDIA" | "BAJA",
          "categoria": "Fraude / Seguridad" | "Facturación / Cobros" | "Operaciones / Cuentas" | "Consultas Generales",
          "motivo": "Explicación breve en español de la clasificación",
          "derivar_a_humano": true | false,
          "metodo_derivacion": "Operador de Emergencias" | "Soporte Comercial" | "Auto-servicio" | "Ejecutivo de Cuentas",
          "respuesta_sugerida": "Una respuesta breve, formal y amable en español reconociendo su caso y guiándolo en los siguientes pasos."
        }}
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "Texto a analizar: \"{text}\"")
        ])

        # Crear la cadena ejecutable
        chain = prompt | self.llm

        try:
            # Ejecutar la inferencia asíncronamente con un timeout controlado
            response = await asyncio.wait_for(
                self.llm.ainvoke(prompt.format(text=request.text)), 
                timeout=self.timeout
            )
            
            response_content = response.content
            logger.info(f"Respuesta cruda del LLM: {response_content}")

            # Procesar y parsear el JSON
            parsed_json = self._extract_json_block(response_content)
            
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Construir la respuesta final y validarla contra el esquema de Pydantic
            return ClassificationResponse(
                prioridad=parsed_json.get("prioridad", "BAJA").upper(),
                categoria=parsed_json.get("categoria", "Consultas Generales"),
                motivo=parsed_json.get("motivo", "Procesado correctamente por el LLM local."),
                derivar_a_humano=parsed_json.get("derivar_a_humano", False),
                metodo_derivacion=parsed_json.get("metodo_derivacion", "Auto-servicio"),
                respuesta_sugerida=parsed_json.get("respuesta_sugerida", "Gracias por contactarnos. Resolveremos tu caso a la brevedad."),
                tiempo_procesamiento_ms=processing_time_ms,
                modelo_utilizado=self.model,
                es_fallback=False
            )

        except asyncio.TimeoutError:
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Inferencia local excedió el timeout de {self.timeout} segundos. Activando fallback heurístico.")
            return self._heuristic_fallback(request.text, processing_time_ms)
            
        except Exception as e:
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Error durante la inferencia local de Ollama: {e}. Activando fallback heurístico.")
            return self._heuristic_fallback(request.text, processing_time_ms)
