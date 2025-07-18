from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import base64
import time
import schedule
import sys
import itertools
from config import PREFECT_USER, PREFECT_PASS, PREFECT_URL

# WebDriver setup
service = Service("./chromedriver.exe")
options = webdriver.ChromeOptions()
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--no-sandbox')

credenciales = f"{PREFECT_USER}:{PREFECT_PASS}"
auth_base64 = base64.b64encode(credenciales.encode()).decode()

def mostrar_spinner(segundos):
    spinner = itertools.cycle(['|', '/', '-', '\\'])
    fin = time.time() + segundos
    while time.time() < fin:
        restante = int(fin - time.time())
        sys.stdout.write(f"\r⏳ Esperando {restante:2d}s {next(spinner)}")
        sys.stdout.flush()
        time.sleep(0.2)
    print("\r✅ Tiempo de espera completado.        ")

def verificar_estado_tareas():
    driver = webdriver.Chrome(service=service, options=options)

    # Agregar encabezado Authorization
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
                    driver.find_element(By.ID, estado).click()
                    time.sleep(2)

                    secciones = driver.find_elements(By.CLASS_NAME, "p-accordion__section")
                    if not secciones:
                        print("⚠ No se encontraron secciones.")
                        continue

                    for idx, seccion in enumerate(secciones, 1):
                        try:
                            boton = seccion.find_element(By.TAG_NAME, "button")
                            boton.click()
                            print(f"🔽 Sección {idx} expandida")
                        except:
                            print(f"⚠ No se pudo expandir sección {idx}")
                            continue

                        try:
                            WebDriverWait(seccion, 5).until(
                                EC.presence_of_element_located((By.CLASS_NAME, "state-list-item__content"))
                            )
                        except:
                            print(f"⚠ Sección {idx} no contiene tarjetas visibles.")
                            continue

                        tarjetas = seccion.find_elements(By.CLASS_NAME, "state-list-item__content")
                        if not tarjetas:
                            print(f"⚠ Sección {idx} sin tarjetas luego del wait.")
                            continue

                        for tarjeta in tarjetas:
                            try:
                                nombre_flujo = tarjeta.find_element(By.CLASS_NAME, "flow-run-bread-crumbs__flow-link").text.strip()
                                alias = tarjeta.find_element(By.CLASS_NAME, "flow-run-bread-crumbs__flow-run-link").text.strip()
                                duracion = tarjeta.find_element(By.CLASS_NAME, "duration-icon-text").text.strip()
                                print(f"🔹 Flujo: {nombre_flujo} > {alias} ({duracion})")
                            except Exception as inner_e:
                                print(f"  ⚠ Error leyendo tarjeta: {inner_e}")

                except Exception as seccion_e:
                    print(f"❌ Error extrayendo {estado}: {seccion_e}")

        mostrar_spinner(10)

    except Exception as e:
        print("❌ Error general:", str(e))

    driver.quit()

# Ejecutar una vez
verificar_estado_tareas()

# Cada 5 minutos
schedule.every(5).minutes.do(verificar_estado_tareas)

try:
    while True:
        schedule.run_pending()
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Ejecución interrumpida por el usuario.")
