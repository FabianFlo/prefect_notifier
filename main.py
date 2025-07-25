import os
import json
import requests
import base64
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from config import PREFECT_USER, PREFECT_PASS, PREFECT_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from firebase_service import init_firebase, agregar_detalle_estado
from selenium.common.exceptions import (TimeoutException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
    StaleElementReferenceException)


db = init_firebase()

MINUTOS_UMBRAL_RUNNING = 15


options = webdriver.ChromeOptions()
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--no-sandbox')
options.add_argument('--headless')
options.add_argument('--log-level=3')
options.add_experimental_option('excludeSwitches', ['enable-logging'])

credenciales = f"{PREFECT_USER}:{PREFECT_PASS}"
auth_base64 = base64.b64encode(credenciales.encode()).decode()


def enviar_telegram(mensaje):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = { "chat_id": TELEGRAM_CHAT_ID, "text": mensaje }
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
        "headers": {"Authorization": f"Basic {auth_base64}"}
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


def realizar_retry(driver, alias_element, max_reintentos=3):
    alias_href = alias_element.get_attribute("href")
    if not alias_href:
        print("❌ No se pudo obtener href del alias")
        return

    for intento in range(max_reintentos):
        try:
            print(f"🌐 Redirigiendo a detalle con: {alias_href}")
            driver.get(alias_href)
            WebDriverWait(driver, 15).until(EC.url_contains("/flow-run/"))
            print("✅ Página de detalle cargada.")
            break
        except Exception as e:
            print(f"❌ Error al abrir el detalle del flujo (intento {intento + 1}): {e}")
            if intento == max_reintentos - 1:
                print("❌ No se pudo abrir el detalle tras varios intentos.")
                return
            time.sleep(2)

    # Retry principal
    for intento in range(max_reintentos):
        try:
            retry_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Retry')]"))
            )
            time.sleep(1)
            retry_btn.click()
            print("🟡 Se hizo clic en Retry principal")
            break
        except Exception as e:
            print(f"  ⚠ Retry principal no clickeable (intento {intento + 1}): {e}")
            if intento == max_reintentos - 1:
                print("❌ No se pudo hacer clic en el botón Retry principal")
                return
            time.sleep(2)

    # Modal de confirmación
    for intento in range(max_reintentos):
        try:
            modal_retry_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH,
                    "//div[contains(@class, 'p-modal__footer')]//button[contains(@class, 'p-button--primary') and .//div[text()[contains(., 'Retry')]]]"
                ))
            )
            time.sleep(1)
            modal_retry_btn.click()
            print("✅ Retry confirmado en el modal.")
            return
        except Exception as e:
            print(f"  ⚠ Modal Retry no clickeable (intento {intento + 1}): {e}")
            if intento == max_reintentos - 1:
                print("❌ No se pudo confirmar Retry en el modal")
                return
            time.sleep(2)



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
    alerta_detectada = False
    driver.find_element(By.ID, estado).click()
    time.sleep(2)

    idx_seccion = 0
    while True:
        secciones = driver.find_elements(By.CLASS_NAME, "p-accordion__section")
        if idx_seccion >= len(secciones):
            break  # no hay más secciones

        for intento_expandir in range(2):
            try:
                secciones_actualizadas = driver.find_elements(By.CLASS_NAME, "p-accordion__section")
                if idx_seccion >= len(secciones_actualizadas):
                    raise IndexError("Sección fuera de rango")
                seccion = secciones_actualizadas[idx_seccion]

                boton = seccion.find_element(By.TAG_NAME, "button")
                boton.click()
                print(f"🔽 Sección {idx_seccion + 1} expandida")

                WebDriverWait(seccion, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "state-list-item__content"))
                )
                break
            except Exception as e:
                print(f"⚠ Intento {intento_expandir + 1} falló expandiendo sección {idx_seccion + 1}: {e}")
                if intento_expandir == 1:
                    print(f"⚠ No se pudo expandir sección {idx_seccion + 1}")
                    idx_seccion += 1
                    continue

        try:
            secciones_actualizadas = driver.find_elements(By.CLASS_NAME, "p-accordion__section")
            if idx_seccion >= len(secciones_actualizadas):
                raise IndexError("Sección fuera de rango")
            seccion = secciones_actualizadas[idx_seccion]
            tarjetas = seccion.find_elements(By.CLASS_NAME, "state-list-item__content")
        except Exception as e:
            print(f"⚠ Error obteniendo tarjetas en sección {idx_seccion + 1}: {e}")
            idx_seccion += 1
            continue

        if not tarjetas:
            print(f"⚠ Sección {idx_seccion + 1} sin tarjetas.")
            idx_seccion += 1
            continue

        idx_t = 0
        while idx_t < len(tarjetas):
            for intento_tarjeta in range(2):
                try:
                    secciones_actualizadas = driver.find_elements(By.CLASS_NAME, "p-accordion__section")
                    if idx_seccion >= len(secciones_actualizadas):
                        raise IndexError("Sección fuera de rango")

                    seccion = secciones_actualizadas[idx_seccion]
                    tarjetas_actualizadas = seccion.find_elements(By.CLASS_NAME, "state-list-item__content")
                    if idx_t >= len(tarjetas_actualizadas):
                        print(f"⚠ Índice {idx_t} fuera de rango en tarjetas actualizadas.")
                        break

                    tarjeta = tarjetas_actualizadas[idx_t]

                    nombre_flujo = tarjeta.find_element(By.CLASS_NAME, "flow-run-bread-crumbs__flow-link").text.strip()
                    alias_element = tarjeta.find_element(By.CLASS_NAME, "flow-run-bread-crumbs__flow-run-link")
                    alias_text = alias_element.text.strip()

                    try:
                        bloque_duracion = tarjeta.find_element(By.CLASS_NAME, "duration-icon-text")
                        duracion = bloque_duracion.find_element(By.CLASS_NAME, "p-icon-text__label").text.strip()
                    except:
                        duracion = "Duración no disponible"

                    mensaje = f"Flujo: {nombre_flujo} > {alias_text} ({duracion})"
                    print(mensaje)

                    # 🚨 alerta para RUNNING prolongado
                    if estado == "running" and not alerta_detectada:
                        match_h = re.search(r"(\d+)h", duracion)
                        match_m = re.search(r"(\d+)m", duracion)
                        horas = int(match_h.group(1)) if match_h else 0
                        minutos = int(match_m.group(1)) if match_m else 0
                        duracion_total_min = horas * 60 + minutos
                        if duracion_total_min >= MINUTOS_UMBRAL_RUNNING:
                            enviar_telegram(mensaje)
                            alerta_detectada = True

                    # 🔁 retry para FALLIDOS
                    if estado == "failed":
                        print("🔁 Intentando retry del flujo fallido...")
                        realizar_retry(driver, alias_element)
                        volver_al_dashboard(driver)

                        # ⏪ Reingresar a pestaña failed y expandir sección actual
                        driver.find_element(By.ID, estado).click()
                        time.sleep(2)

                        secciones = driver.find_elements(By.CLASS_NAME, "p-accordion__section")
                        if idx_seccion < len(secciones):
                            try:
                                boton = secciones[idx_seccion].find_element(By.TAG_NAME, "button")
                                boton.click()
                                print(f"🔽 Reexpandida sección {idx_seccion + 1} tras retry")
                                WebDriverWait(secciones[idx_seccion], 5).until(
                                    EC.presence_of_element_located((By.CLASS_NAME, "state-list-item__content"))
                                )
                            except Exception as e:
                                print(f"⚠ No se pudo reexpandir sección tras retry: {e}")

                        alerta_detectada = True

                        # ⚠ Recargar tarjetas luego del reload
                        tarjetas = secciones[idx_seccion].find_elements(By.CLASS_NAME, "state-list-item__content")
                        idx_t += 1
                        break  # salir del intento_tarjeta

                    break  # tarjeta procesada correctamente
                except StaleElementReferenceException as se:
                    print(f"  ⚠ Stale element en tarjeta {idx_t + 1} (intento {intento_tarjeta + 1}): {se}")
                except Exception as e:
                    print(f"  ⚠ Error leyendo tarjeta {idx_t + 1} (intento {intento_tarjeta + 1}): {e}")
                    if intento_tarjeta == 1:
                        continue

            idx_t += 1

        idx_seccion += 1

    return alerta_detectada



def verificar_estado_tareas():
    driver = setup_driver()
    driver.get(PREFECT_URL)
    time.sleep(5)

    try:
        resultados = contar_tareas_por_estado(driver)

        running_alert = False
        failed_alert = False

        print(f"\n➡ Entrando al detalle de: RUNNING")
        if procesar_estado(driver, "running"):
            running_alert = True

        if resultados.get("failed", 0) > 0:
            print(f"\n➡ Entrando al detalle de: FAILED")
            if procesar_estado(driver, "failed"):
                failed_alert = True

        if running_alert or failed_alert:
            agregar_detalle_estado(
                failed=resultados.get("failed", 0) if failed_alert else 0,
                running=1 if running_alert else 0,
                scheduled=resultados.get("scheduled", 0)
            )

    except Exception as e:
        print("❌ Error general:", str(e))
    finally:
        driver.quit()


if __name__ == "__main__":
    verificar_estado_tareas()
