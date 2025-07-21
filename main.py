import os
import json
import requests
import base64
import re
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from config import PREFECT_USER, PREFECT_PASS, PREFECT_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Configuración
MINUTOS_UMBRAL = 40  # solo notificar si la duración supera este valor

# WebDriver setup
options = webdriver.ChromeOptions()
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--no-sandbox')
options.add_argument('--headless')  # ✅ oculto para uso en cron

credenciales = f"{PREFECT_USER}:{PREFECT_PASS}"
auth_base64 = base64.b64encode(credenciales.encode()).decode()


def enviar_telegram(mensaje):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje
    }

    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("✅ Mensaje enviado al grupo Telegram")
        else:
            print("❌ Error Telegram:", response.text)
    except Exception as e:
        print("❌ Excepción al enviar Telegram:", str(e))


def setup_driver():
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {
        "headers": {
            "Authorization": f"Basic {auth_base64}"
        }
    })
    return driver


def contar_tareas_por_estado(driver):
    estados = ["failed", "running", "scheduled"]
    resultados = {}
    print("📊 Conteo por estado:")
    for estado in estados:
        try:
            li = driver.find_element(By.ID, estado)
            valor_span = li.find_element(By.CLASS_NAME, "flow-run-state-type-count__value")
            valor = int(valor_span.text.strip())
            resultados[estado] = valor
            print(f" - {estado}: {valor}")
        except:
            resultados[estado] = 0
            print(f" - {estado}: Error al obtener")
    return resultados


def realizar_retry(driver, alias_element):
    alias_element.click()
    WebDriverWait(driver, 15).until(EC.url_contains("/flow-run/"))
    print("✅ Página de detalle cargada.")

    retry_btn = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Retry')]"))
    )
    time.sleep(1)
    retry_btn.click()
    print("🟡 Se hizo clic en Retry principal")

    try:
        modal_retry_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH,
                "//div[contains(@class, 'p-modal__footer')]//button[contains(@class, 'p-button--primary') and .//div[text()[contains(., 'Retry')]]]"
            ))
        )
        time.sleep(1)
        modal_retry_btn.click()
        print("✅ Retry confirmado en el modal.")
    except Exception as modal_e:
        print("❌ No se pudo confirmar Retry en el modal:", str(modal_e))


def volver_al_dashboard(driver):
    try:
        dashboard_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.p-context-nav-item[href="/dashboard"]'))
        )
        dashboard_btn.click()
        WebDriverWait(driver, 10).until(EC.url_contains("/dashboard"))
        print("↩ Volviendo al dashboard.")
        time.sleep(3)
    except:
        print("⚠ No se pudo volver al dashboard.")


def procesar_estado(driver, estado):
    driver.find_element(By.ID, estado).click()
    time.sleep(2)

    secciones = driver.find_elements(By.CLASS_NAME, "p-accordion__section")
    if not secciones:
        print("⚠ No se encontraron secciones.")
        return

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
                alias_element = tarjeta.find_element(By.CLASS_NAME, "flow-run-bread-crumbs__flow-run-link")
                alias_text = alias_element.text.strip()

                try:
                    duracion = tarjeta.find_element(By.CLASS_NAME, "duration-icon-text").text.strip()
                except:
                    duracion = "Duración no disponible"

                mensaje = f"Flujo: {nombre_flujo} > {alias_text} ({duracion})"
                print(mensaje)

                if estado == "running":
                    match = re.search(r"(\d+)m", duracion)
                    minutos = int(match.group(1)) if match else 0
                    if minutos >= MINUTOS_UMBRAL:
                        enviar_telegram(mensaje)

                if estado == "failed":
                    print("🔁 Intentando retry del flujo fallido...")
                    realizar_retry(driver, alias_element)
                    volver_al_dashboard(driver)

            except Exception as inner_e:
                print(f"  ⚠ Error leyendo tarjeta: {inner_e}")


def registrar_estado_por_hora(failed, running, scheduled):
    resumen_path = "resumen/resumen.json"
    hora_actual = datetime.now().strftime("%H:%M")

    nuevo_detalle = {
        "hora": hora_actual,
        "failed": failed,
        "running": running,
        "scheduled": scheduled
    }

    if os.path.exists(resumen_path):
        with open(resumen_path, "r") as f:
            resumen = json.load(f)
    else:
        resumen = {"ejecuciones": 0, "fallos": 0, "detalle": []}

    resumen["ejecuciones"] += 1
    resumen["fallos"] += failed
    resumen["detalle"].append(nuevo_detalle)

    with open(resumen_path, "w") as f:
        json.dump(resumen, f, indent=2)

    print("📝 Estado registrado en resumen.json")


def verificar_estado_tareas():
    driver = setup_driver()
    driver.get(PREFECT_URL)
    time.sleep(5)

    try:
        resultados = contar_tareas_por_estado(driver)

        # Registrar resumen por hora
        registrar_estado_por_hora(
            failed=resultados.get("failed", 0),
            running=resultados.get("running", 0),
            scheduled=resultados.get("scheduled", 0)
        )

        for estado, valor in resultados.items():
            if valor >= 1:
                print(f"\n➡ Entrando al detalle de: {estado.upper()}")
                procesar_estado(driver, estado)

    except Exception as e:
        print("❌ Error general:", str(e))
    finally:
        driver.quit()


if __name__ == "__main__":
    verificar_estado_tareas()
