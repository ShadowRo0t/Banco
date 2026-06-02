# --- Etapa 1: Constructor de dependencias ---
FROM python:3.12-slim AS builder

WORKDIR /build

# Instalar dependencias del sistema necesarias para compilar paquetes
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python en el directorio del usuario local
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# --- Etapa 2: Imagen final de producción ---
FROM python:3.12-slim AS runner

WORKDIR /app

# Crear usuario y grupo no-root por seguridad
RUN groupadd --system --gid 1001 appgroup && \
    useradd --system --uid 1001 --gid 1001 -m appuser

# Copiar dependencias de Python construidas en la primera etapa
COPY --from=builder /root/.local /home/appuser/.local

# Copiar el código fuente de la aplicación
COPY app/ /app/app/

# Asegurar variables de entorno de Python y de ruta
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV APP_ENV=production

# Modificar permisos del directorio para el usuario no-root
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

# Comando para ejecutar la aplicación con uvicorn y alta concurrencia
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
