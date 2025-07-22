import os
import json
import matplotlib.pyplot as plt
import requests
import numpy as np
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from firebase_service import init_firebase

db = init_firebase()

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

def generar_grafico_resumen_firebase():
    resumenes_ref = db.collection("resumenes")
    docs = resumenes_ref.stream()

    data = []
    for doc in docs:
        item = doc.to_dict()
        item_id = doc.id
        if item.get("test", False):
            continue  # Ignorar si es test
        item["hora"] = item.get("hora", item_id)  # Si no hay campo hora, usar doc.id
        data.append(item)

    if not data:
        print("⚠️ No hay datos válidos en Firebase para graficar.")
        return

    # Ordenar por hora
    data.sort(key=lambda x: x["hora"])

    horas = [item["hora"] for item in data]
    failed = [max(0, item.get("failed", 0)) for item in data]
    running = [max(0, item.get("running", 0)) for item in data]
    scheduled = [max(0, item.get("scheduled", 0)) for item in data]

    fallos = sum(failed)

    plt.figure(figsize=(18, 7))

    plt.plot(horas, failed, label="Failed", marker='o', color='red', linewidth=2, alpha=0.9)
    plt.plot(horas, running, label="Running", marker='o', color='blue', linewidth=2, alpha=0.7)
    plt.plot(horas, scheduled, label="Scheduled", marker='o', color='orange', linewidth=2, alpha=0.7)

    plt.fill_between(horas, failed, color='red', alpha=0.05)
    plt.fill_between(horas, running, color='blue', alpha=0.05)
    plt.fill_between(horas, scheduled, color='orange', alpha=0.05)

    for i, val in enumerate(failed):
        if val > 0:
            plt.scatter(horas[i], val, color='darkred', s=60, zorder=5)

    plt.xticks(ticks=range(0, len(horas), 2), labels=[horas[i] for i in range(0, len(horas), 2)], rotation=45)

    todos = failed + running + scheduled
    limite_y_max = max(todos) + 5 if todos else 10
    plt.ylim(bottom=0, top=limite_y_max)

    plt.title(f"Resumen diario de Prefect", fontsize=14)
    plt.xlabel("Hora", fontsize=12)
    plt.ylabel("Cantidad", fontsize=12)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    output_path = "reporte_diario.png"
    plt.savefig(output_path)
    print(f"📊 Gráfico generado desde Firebase y guardado en {output_path}")

    mensaje = f"📊 Resumen diario de Prefect"
    enviar_imagen_telegram(output_path, mensaje=mensaje)
    os.remove(output_path)

if __name__ == "__main__":
    generar_grafico_resumen_firebase()
