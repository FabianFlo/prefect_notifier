from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
import base64
import time
import schedule
from config import PREFECT_USER, PREFECT_PASS, PREFECT_URL  # Importa desde config.py

# Configurar WebDriver
service = Service("./chromedriver.exe")
options = webdriver.ChromeOptions()
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--no-sandbox')

# Codificar credenciales en base64 para autorización
credenciales = f"{PREFECT_USER}:{PREFECT_PASS}"
auth_base64 = base64.b64encode(credenciales.encode()).decode()

def verificar_estado_tareas():
    driver = webdriver.Chrome(service=service, options=options)

    # Inyectar header Authorization
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {
        "headers": {
            "Authorization": f"Basic {auth_base64}"
        }
    })

    driver.get(PREFECT_URL)
    time.sleep(5)

    estados = ["failed", "running", "scheduled"]
    resultados = {}

    try:
        print("📊 Conteo por estado:")
        for estado in estados:
            try:
                li = driver.find_element(By.ID, estado)
                valor_span = li.find_element(By.CLASS_NAME, "flow-run-state-type-count__value")
                valor = int(valor_span.text.strip())
                resultados[estado] = valor
                print(f" - {estado}: {valor}")
            except Exception:
                resultados[estado] = 0
                print(f" - {estado}: Error al obtener")

        for estado, valor in resultados.items():
            if valor >= 1:
                print(f"\n➡ Entrando al detalle de: {estado.upper()}")
                try:
                    seccion = driver.find_element(By.ID, estado)
                    seccion.click()
                    time.sleep(2)

                    tarjetas = driver.find_elements(By.CLASS_NAME, "state-list-item__content")

                    if not tarjetas:
                        print("⚠ No se encontraron ejecuciones en esta sección.")
                        continue

                    for tarjeta in tarjetas:
                        try:
                            nombre_flujo = tarjeta.find_element(By.CLASS_NAME, "flow-run-bread-crumbs__flow-link").text.strip()
                            alias = tarjeta.find_element(By.CLASS_NAME, "flow-run-bread-crumbs__flow-run-link").text.strip()
                            duracion = tarjeta.find_element(By.CLASS_NAME, "duration-icon-text").text.strip()
                            print(f"🔹 Flujo: {nombre_flujo} > {alias} ({duracion})")
                        except Exception as inner_e:
                            print(f"  ⚠ Error en tarjeta: {inner_e}")

                except Exception as seccion_e:
                    print(f"❌ No se pudo extraer detalle de {estado}: {seccion_e}")

        print("⏳ Esperando 10 segundos para vista...")
        time.sleep(10)

    except Exception as e:
        print("❌ Error general:", str(e))

    driver.quit()

# Ejecutar una vez al inicio
verificar_estado_tareas()

# Programación recurrente
schedule.every(5).minutes.do(verificar_estado_tareas)

while True:
    schedule.run_pending()
    time.sleep(1)
