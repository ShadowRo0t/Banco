import asyncio
import httpx
import time
import random
import sys

# URL base de la API (ajustable por argumento)
API_URL = "http://localhost:8000/classify"

# Muestra de prompts de prueba para simular tráfico bancario real
PROMPTS = [
    # ALTA PRIORIDAD (Seguridad y Fraudes)
    "URGENTE: Me acaban de clonar la tarjeta de débito y veo cobros de mil dólares que no hice hoy en la mañana!",
    "Hola, perdí mi billetera y necesito bloquear mi tarjeta de crédito inmediatamente por sospecha de fraude.",
    "Alguien hackeó mi cuenta de banca móvil. Cambiaron mi contraseña y están haciendo transferencias a terceros.",
    "¡Alerta de estafa! Me llegó un mensaje de texto de phishing y creo que ingresé mis credenciales en un sitio falso.",
    "Me cobraron compras por internet que yo no autoricé. Exijo el bloqueo inmediato de mi cuenta.",
    
    # MEDIA PRIORIDAD (Facturación y Operaciones comerciales)
    "Hola, tengo una discrepancia en mi estado de cuenta. Me cobraron dos veces la suscripción mensual.",
    "Tengo problemas para renovar mi tarjeta de débito que vence a fin de este mes. ¿Me la pueden enviar a casa?",
    "Hice una transferencia de fondos entre mis cuentas pero la aplicación dio error y no veo el saldo reflejado.",
    "Hola, deseo disputar una comisión por mantenimiento mensual de cuenta corriente que considero improcedente.",
    "¿Cómo puedo aumentar el límite de crédito diario para hacer transferencias por internet?",
    
    # BAJA PRIORIDAD (Consultas Generales)
    "¿Podrían informarme en qué horario atienden los sábados en la sucursal de Las Condes?",
    "Hola, me gustaría saber cuántos puntos de fidelidad acumulados tengo en mi tarjeta de beneficios.",
    "¿Cuáles son los requisitos y la tasa de interés actual para solicitar un crédito hipotecario de vivienda?",
    "¿Tienen sucursales abiertas que tengan cajeros aptos para depósitos en efectivo cerca de Providencia?",
    "Hola, solo quería consultar si la aplicación móvil del banco es compatible con el nuevo iOS."
]

async def send_request(client: httpx.AsyncClient, req_id: int):
    prompt = random.choice(PROMPTS)
    payload = {"text": prompt}
    start = time.perf_counter()
    try:
        response = await client.post(API_URL, json=payload, timeout=15.0)
        latency = (time.perf_counter() - start) * 1000
        if response.status_code == 200:
            data = response.json()
            print(f"[Req {req_id:03d}] OK - Latencia: {latency:.1f}ms - Prioridad: {data['prioridad']} | Método: {data['metodo_derivacion']} (Fallback: {data['es_fallback']})")
            return response.status_code, data['prioridad']
        else:
            print(f"[Req {req_id:03d}] ERROR {response.status_code} - Latencia: {latency:.1f}ms")
            return response.status_code, None
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        print(f"[Req {req_id:03d}] CRITICAL ERROR - {type(e).__name__} tras {latency:.1f}ms")
        return 500, None

async def run_load_test(concurrency: int, total_requests: int):
    print("=" * 70)
    print(f"Iniciando Simulador de Carga Bancaria y Pruebas de Estrés")
    print(f"URL de la API: {API_URL}")
    print(f"Concurrencia: {concurrency} peticiones simultáneas")
    print(f"Total peticiones a enviar: {total_requests}")
    print("=" * 70)
    
    limits = httpx.Limits(max_keepalive_connections=concurrency, max_connections=concurrency * 2)
    async with httpx.AsyncClient(limits=limits) as client:
        # Enviar en ráfagas de concurrencia
        tasks = []
        results = []
        
        start_time = time.perf_counter()
        
        for i in range(1, total_requests + 1):
            tasks.append(send_request(client, i))
            if len(tasks) >= concurrency or i == total_requests:
                batch_results = await asyncio.gather(*tasks)
                results.extend(batch_results)
                tasks = []
                # Pequeña pausa para no colapsar instantáneamente los hilos locales
                await asyncio.sleep(0.05)
                
        total_duration = time.perf_counter() - start_time
        
        # Procesar resumen de métricas
        status_codes = [r[0] for r in results]
        priorities = [r[1] for r in results if r[1] is not None]
        
        success_count = status_codes.count(200)
        error_count = len(status_codes) - success_count
        
        print("\n" + "=" * 70)
        print("RESUMEN DE PRUEBA DE ESTRÉS")
        print("=" * 70)
        print(f"Tiempo Total: {total_duration:.2f} segundos")
        print(f"Peticiones por Segundo (RPS): {total_requests / total_duration:.2f}")
        print(f"Peticiones Exitosas (200 OK): {success_count} ({success_count/total_requests*100:.1f}%)")
        print(f"Peticiones Fallidas/Errores: {error_count} ({error_count/total_requests*100:.1f}%)")
        
        if priorities:
            print("\nDistribución de Prioridades Clasificadas:")
            for p in ["ALTA", "MEDIA", "BAJA"]:
                p_count = priorities.count(p)
                print(f" - {p}: {p_count} ({p_count/len(priorities)*100:.1f}%)")
        print("=" * 70)

if __name__ == "__main__":
    # Obtener argumentos
    concurrency = 5
    total_requests = 100
    
    if len(sys.argv) > 1:
        try:
            concurrency = int(sys.argv[1])
        except ValueError:
            pass
    if len(sys.argv) > 2:
        try:
            total_requests = int(sys.argv[2])
        except ValueError:
            pass
            
    asyncio.run(run_load_test(concurrency, total_requests))
