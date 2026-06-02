# Sistema Local de Clasificación y Priorización de Incidentes Bancarios

Este proyecto proporciona una solución tecnológica de nivel industrial para automatizar la clasificación de solicitudes de clientes bancarios (provenientes de chats y transcripciones telefónicas) en tiempo real. 

Utilizando un **Modelo de Lenguaje Local (LLM)** a través de **Ollama** y el framework **LangChain**, el sistema categoriza las solicitudes y detecta su nivel de urgencia sin enviar datos confidenciales a la nube pública, garantizando así la absoluta privacidad de los datos financieros.

---

## 🚀 Arquitectura y Componentes del Sistema

El ecosistema está diseñado bajo principios de resiliencia, contenedores desacoplados y observabilidad en tiempo real:

1. **Software (FastAPI + LangChain + Ollama)**: API REST asíncrona con validaciones de tipo estrictas mediante Pydantic y extracción de JSON estructurado del LLM local con un mecanismo de *Fallback Heurístico* redundante (Regex).
2. **Observabilidad (Prometheus + Grafana)**: Instrumentación de métricas personalizadas (RPS, latencias de la API, tiempos exclusivos de inferencia LLM y distribución de prioridades).
3. **Orquestación (Docker + Kubernetes)**: Manifiestos listos para producción con balanceo de carga, autoprovisionamiento del modelo LLM, ingress y autoescalado horizontal (HPA).
4. **Pipeline CI/CD (GitHub Actions)**: Integración continua que ejecuta tests automáticos unitarios en cada push, construye la imagen Docker y la sube al registro.

---

## 📂 Estructura del Repositorio

```text
├── .github/
│   └── workflows/
│       └── ci-cd.yml         # Pipeline CI/CD de GitHub Actions
├── app/
│   ├── tests/
│   │   └── test_main.py      # Pruebas unitarias de la API (mocking de Ollama)
│   ├── config.py             # Configuración de variables (Pydantic Settings)
│   ├── main.py               # Punto de entrada de FastAPI y métricas Prometheus
│   ├── schemas.py            # Modelos de validación de datos Pydantic
│   └── services.py           # Servicio LangChain + Ollama y Fallback Heurístico
├── k8s/
│   ├── api-configmap.yaml    # Configuración de variables de entorno de producción
│   ├── api-deployment.yaml   # Despliegue de la API (2 réplicas, resource limits)
│   ├── api-service.yaml      # Service ClusterIP de la API
│   ├── api-ingress.yaml      # Enrutamiento externo (Ingress NGINX)
│   ├── api-hpa.yaml          # Autoescalador HPA (escala de 2 a 10 pods a >75% CPU)
│   ├── ollama-deployment.yaml# Despliegue de Ollama con PVC de persistencia y autodescarga
│   ├── ollama-service.yaml   # Service ClusterIP de Ollama
│   └── monitoring/
│       ├── prometheus-config.yaml      # CM de descubrimiento dinámico de pods
│       ├── prometheus-deployment.yaml  # Deployment y RBAC de Prometheus
│       ├── prometheus-service.yaml     # Service ClusterIP de Prometheus
│       ├── grafana-deployment.yaml     # Deployment y autoprovisionamiento de Grafana
│       ├── grafana-service.yaml        # Service NodePort para acceso externo
│       └── grafana-dashboard.json      # Definición exportable del Dashboard
├── Dockerfile                # Dockerfile multi-stage optimizado (no-root user)
├── docker-compose.yml        # Orquestación de desarrollo local rápida
├── prometheus.yml            # Configuración de scrapeo para docker-compose
├── requirements.txt          # Dependencias de Python
├── simulate_load.py          # Script simulador de carga concurrente y pruebas de estrés
└── README.md                 # Documentación técnica
```

---

## 🛠️ Guía 1: Desarrollo Local y Pruebas Unitarias

Sigue estos pasos para ejecutar y probar la API en tu estación de trabajo sin Docker:

### 1. Requisitos Previos
- **Python 3.12** o superior instalado.
- **Ollama** instalado y ejecutándose en tu host (`http://localhost:11434`).
- Asegúrate de contar con el modelo `llama3.2:3b` descargado localmente (ejecuta en la terminal `ollama pull llama3.2:3b`).

### 2. Configurar Entorno Virtual e Instalar Dependencias
```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# En Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# En Linux/macOS:
source venv/bin/activate

# Instalar dependencias requeridas
pip install -r requirements.txt
pip install pytest pytest-asyncio
```

### 3. Ejecutar las Pruebas Unitarias (Automáticas y Deterministas)
Las pruebas unitarias utilizan **mocking** para simular la respuesta del LLM local de manera instantánea y determinista, simulando además el comportamiento del fallback heurístico. Es la misma suite que se ejecuta en el pipeline CI/CD de GitHub Actions:
```bash
pytest -v
```

### 4. Lanzar la API en modo Desarrollo
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- **Documentación Interactiva (Swagger UI)**: Accede en [http://localhost:8000/docs](http://localhost:8000/docs)
- **Métricas Prometheus**: Accede en [http://localhost:8000/metrics](http://localhost:8000/metrics)
- **Endpoint de Salud**: Accede en [http://localhost:8000/health](http://localhost:8000/health)

---

## 🐳 Guía 2: Despliegue Local con Docker Compose

Para levantar de manera unificada la API, el servidor de Prometheus y la interfaz visual de Grafana, ejecutándose integrados:

### 1. Iniciar el Entorno
Ejecuta el siguiente comando en la raíz del repositorio:
```bash
docker-compose up --build -d
```
*Nota: La API en Docker se conectará automáticamente a tu instancia local de Ollama en el Host de Windows a través de `host.docker.internal` para evitar la descarga repetida de 2GB de modelos dentro del contenedor.*

### 2. Acceder a los Servicios
- **FastAPI API**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Prometheus Console**: [http://localhost:9090](http://localhost:9090)
- **Grafana Dashboard**: [http://localhost:3000](http://localhost:3000)
  - *Credenciales de acceso*: Usuario `admin` | Contraseña `admin` (o haz clic en "Saltar" si la sesión anónima de administrador está activada).
  - *Dashboard Pre-Cargado*: Navega a **Dashboards** y verás el panel **"Banco  - Control de Incidentes y LLM"** ya configurado y conectado a los datos de la API.

---

## 🧪 Simulación de Carga

Para probar el comportamiento del sistema ante picos de demanda o realizar pruebas de estrés, puedes utilizar el script `simulate_load.py`.

### 1. Ejecutar la Simulación
```bash
python simulate_load.py
```

### 2. Opciones Disponibles
El script permite ajustar los parámetros de la prueba:
- `--concurrency`: Número de peticiones simultáneas (default: 10).
- `--total-requests`: Número total de peticiones a realizar (default: 50).

**Ejemplo con parámetros personalizados:**
```bash
python simulate_load.py --concurrency 50 --total-requests 500
```

### 3. Resultados
Al finalizar, el script mostrará métricas agregadas como el tiempo promedio de respuesta, el porcentaje de errores y el tiempo total de ejecución.

---

## ☸️ Guía 3: Despliegue Completo en Kubernetes

Esta infraestructura está configurada para desplegarse de manera autónoma en cualquier clúster local (como Minikube, Kind o K3s).

### 1. Aplicar la Configuración Básica y Ollama
```bash
# 1. Crear ConfigMap de variables
kubectl apply -f k8s/api-configmap.yaml

# 2. Desplegar Ollama (PVC para modelos + Deployment + Service)
# El pod de Ollama descargará automáticamente el modelo llama3.2:3b al iniciar mediante un hook postStart
kubectl apply -f k8s/ollama-deployment.yaml
kubectl apply -f k8s/ollama-service.yaml
```

### 2. Desplegar la API y su Escalabilidad
```bash
# 3. Desplegar la API de clasificación bancaria (2 réplicas)
kubectl apply -f k8s/api-deployment.yaml

# 4. Crear el Service interno
kubectl apply -f k8s/api-service.yaml

# 5. Crear el Ingress (Enrutador de tráfico)
kubectl apply -f k8s/api-ingress.yaml

# 6. Activar el Autoescalador HPA
kubectl apply -f k8s/api-hpa.yaml
```

### 3. Desplegar la Pila de Observabilidad (Monitoreo)
```bash
# 7. Configurar Prometheus (RBAC + Configuración de auto-descubrimiento)
kubectl apply -f k8s/monitoring/prometheus-config.yaml
kubectl apply -f k8s/monitoring/prometheus-deployment.yaml
kubectl apply -f k8s/monitoring/prometheus-service.yaml

# 8. Configurar Grafana (Aprovisionamiento de Data Sources y Dashboards automatizado)
kubectl apply -f k8s/monitoring/grafana-dashboard-configmap.yaml
kubectl apply -f k8s/monitoring/grafana-deployment.yaml
kubectl apply -f k8s/monitoring/grafana-service.yaml
```

### 4. Acceder al Dashboard de Grafana en Kubernetes
Grafana está expuesto mediante un servicio de tipo `NodePort`. Si utilizas Minikube, puedes obtener la URL de acceso directa con:
```bash
minikube service grafana-service --url
# O bien, realiza un port-forward estándar:
kubectl port-forward svc/grafana-service 3000:3000
```
Abre tu navegador en `http://localhost:3000`, ingresa con `admin`/`admin`, y haz clic en el dashboard **"Banco - Control de Incidentes y LLM"**. ¡Verás todas las métricas en tiempo real sin requerir ninguna acción manual!

---

## 📈 Guía 4: Simulación de Carga y Prueba del HPA

El repositorio incluye un script asíncrono avanzado (`simulate_load.py`) para simular ráfagas concurrentes de solicitudes de clientes, poblar los paneles de Grafana y poner a prueba los límites de la API para disparar el autoescalado horizontal (HPA).

Para ejecutarlo desde tu consola local (asegúrate de tener el entorno virtual activado):
```bash
# Sintaxis: python simulate_load.py [concurrencia] [total_peticiones]
# Ejemplo: Enviar 250 peticiones enviadas de a 10 concurrentes simultáneas:
python simulate_load.py 10 250
```

### Resultados de la Simulación en la Consola
El script enviará prompts aleatorios realistas (desde denuncias de clonación críticas hasta preguntas simples de horarios) y mostrará el estado de la respuesta y la latencia en tiempo real:
```text
[Req 001] OK - Latencia: 245.2ms - Prioridad: ALTA | Método: Operador de Emergencias / Prevención de Fraude (Fallback: False)
[Req 002] OK - Latencia: 15.0ms - Prioridad: BAJA | Método: Auto-servicio (Fallback: False)
[Req 003] OK - Latencia: 180.5ms - Prioridad: MEDIA | Método: Soporte Comercial / Ejecutivo de Cuentas (Fallback: False)
...
======================================================================
RESUMEN DE PRUEBA DE ESTRÉS
======================================================================
Tiempo Total: 12.35 segundos
Peticiones por Segundo (RPS): 20.24
Peticiones Exitosas (200 OK): 250 (100.0%)
Peticiones Fallidas/Errores: 0 (0.0%)

Distribución de Prioridades Clasificadas:
 - ALTA: 92 (36.8%)
 - MEDIA: 81 (32.4%)
 - BAJA: 77 (30.8%)
======================================================================
```

### 🔍 Comportamiento Esperado bajo Estrés (40% Resiliencia)
1. **Validación del Fallback Heurístico**: Si deseas probar la robustez extrema del sistema ante fallos críticos, detén temporalmente tu servidor local de Ollama (`docker stop` u `ollama stop`) y ejecuta el script de carga de nuevo. Verás que las peticiones se procesan en menos de **5 milisegundos** con un 100% de éxito, utilizando el algoritmo inteligente de palabras clave Regex y asignando perfectamente las prioridades ALTA, MEDIA y BAJA sin caídas de servicio (500).
2. **Validación del HPA en Kubernetes**: Al enviar ráfagas masivas al clúster (ej. `python simulate_load.py 30 1000`), el HPA detectará que el consumo promedio de CPU de los pods de la API supera el 75% y ordenará de inmediato levantar nuevas réplicas (escalando de 2 a un número superior de pods según sea necesario), garantizando alta disponibilidad sin intervención manual. Puedes monitorear el estado del HPA en tiempo real ejecutando:
   ```bash
   kubectl get hpa -w
   ```
