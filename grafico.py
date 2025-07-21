import os
import json
import matplotlib.pyplot as plt
import requests
import numpy as np
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def enviar_imagen_telegram(imagen_path, mensaje="📊 Reporte diario de flujos"):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Faltan variables de entorno para Telegram")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    with open(imagen_path, 'rb') as img:
        files = {'photo': img}
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'caption': mensaje
        }
        response = requests.post(url, files=files, data=data)
        if response.status_code == 200:
            print("✅ Imagen enviada por Telegram")
        else:
            print("❌ Error al enviar imagen:", response.text)

def generar_grafico_resumen():
    resumen_path = "resumen/resumen.json"

    with open(resumen_path, "r") as file:
        json_data = json.load(file)

    ejecuciones = json_data.get("ejecuciones", 0)
    fallos = json_data.get("fallos", 0)
    data = json_data.get("detalle", [])

    horas = [item["hora"] for item in data]
    failed = [max(0, item["failed"]) for item in data]
    running = [max(0, item["running"]) for item in data]
    scheduled = [max(0, item["scheduled"]) for item in data]

    plt.figure(figsize=(18, 7))

    # Líneas principales
    plt.plot(horas, failed, label="Failed", marker='o', color='red', linewidth=2, alpha=0.9)
    plt.plot(horas, running, label="Running", marker='o', color='orange', linewidth=2, alpha=0.7)
    plt.plot(horas, scheduled, label="Scheduled", marker='o', color='green', linewidth=2, alpha=0.7)

    # Sombreado
    plt.fill_between(horas, failed, color='red', alpha=0.05)
    plt.fill_between(horas, running, color='orange', alpha=0.05)
    plt.fill_between(horas, scheduled, color='green', alpha=0.05)

    # Marcar valores de fallos
    for i, val in enumerate(failed):
        if val > 0:
            plt.scatter(horas[i], val, color='darkred', s=60, zorder=5)

    # Etiquetas X más espaciadas
    plt.xticks(ticks=range(0, len(horas), 2), labels=[horas[i] for i in range(0, len(horas), 2)], rotation=45)

    # Eje Y fijo desde 0 hasta el máximo valor + margen
    todos = failed + running + scheduled
    limite_y_max = max(todos) + 5 if todos else 10
    plt.ylim(bottom=0, top=limite_y_max)

    # Título
    plt.title(f"Resumen diario de Prefect\nEjecuciones: {ejecuciones} | Fallos de ejecución: {fallos}", fontsize=14)
    plt.xlabel("Hora", fontsize=12)
    plt.ylabel("Cantidad", fontsize=12)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    # Guardar y enviar imagen
    output_path = "reporte_diario.png"
    plt.savefig(output_path)
    print(f"📊 Gráfico guardado en {output_path}")

    mensaje = f"📊 Resumen diario de Prefect\n🟢 Ejecuciones: {ejecuciones} | 🔴 Fallos: {fallos}"
    enviar_imagen_telegram(output_path, mensaje=mensaje)
    os.remove(output_path)

    # Respaldar y eliminar resumen.json
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    respaldo_path = f"resumen/resumen_{fecha_hoy}.json"
    os.rename(resumen_path, respaldo_path)
    print(f"🗂️ Resumen respaldado como {resumen_path} → {respaldo_path}")

if __name__ == "__main__":
    generar_grafico_resumen()
