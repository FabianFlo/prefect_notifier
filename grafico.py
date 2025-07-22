import os
import json
import matplotlib.pyplot as plt
import requests
from collections import defaultdict
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


def agrupar_por_hora(data):
    resumen_por_hora = defaultdict(lambda: {"failed": 0, "running": 0, "scheduled": 0})

    for item in data:
        if item.get("test"):
            continue

        hora_str = item.get("hora", "")
        hora_entera = f"{hora_str.split(':')[0].zfill(2)}:00"  # "8:15" -> "08:00"
        resumen_por_hora[hora_entera]["failed"] += item.get("failed", 0)
        resumen_por_hora[hora_entera]["running"] += item.get("running", 0)
        resumen_por_hora[hora_entera]["scheduled"] += item.get("scheduled", 0)

    horas_ordenadas = [f"{str(h).zfill(2)}:00" for h in range(24)]
    failed = [resumen_por_hora[h]["failed"] for h in horas_ordenadas]
    running = [resumen_por_hora[h]["running"] for h in horas_ordenadas]
    scheduled = [resumen_por_hora[h]["scheduled"] for h in horas_ordenadas]

    return horas_ordenadas, failed, running, scheduled


def borrar_resumenes_diarios():
    resumenes_ref = db.collection("resumenes")
    docs = resumenes_ref.stream()

    eliminados = 0
    for doc in docs:
        data = doc.to_dict()
        if not data.get("test", False):
            resumenes_ref.document(doc.id).delete()
            eliminados += 1

    print(f"🧹 Se eliminaron {eliminados} documentos de la colección 'resumenes' (excepto test)")


def generar_grafico_resumen_firebase():
    resumenes_ref = db.collection("resumenes")
    docs = resumenes_ref.stream()

    data = []
    for doc in docs:
        item = doc.to_dict()
        item_id = doc.id
        if item.get("test", False):
            continue  # Ignorar si es test
        item["hora"] = item.get("hora", item_id)
        data.append(item)

    if not data:
        print("⚠️ No hay datos válidos en Firebase para graficar.")
        return

    horas, failed, running, scheduled = agrupar_por_hora(data)
    fallos = sum(failed)

    # Coordenadas centradas (00.5, 01.5, ..., 23.5)
    x = [i + 0.5 for i in range(24)]
    x_labels = horas  # etiquetas tipo "00:00", ..., "23:00"

    plt.figure(figsize=(18, 7))

    plt.plot(x, failed, label="Failed", marker='o', color='red', linewidth=2, alpha=0.9)
    plt.plot(x, scheduled, label="Scheduled", marker='o', color='orange', linewidth=2, alpha=0.7)
    plt.plot(x, running, label="Prolonged Running", marker='o', color='blue', linewidth=2, alpha=0.7)

    plt.fill_between(x, failed, color='red', alpha=0.05)
    plt.fill_between(x, scheduled, color='orange', alpha=0.05)
    plt.fill_between(x, running, color='blue', alpha=0.05)

    for i, val in enumerate(failed):
        if val > 0:
            plt.scatter(x[i], val, color='darkred', s=60, zorder=5)

    plt.xticks(ticks=range(24), labels=x_labels, rotation=45)

    todos = failed + running + scheduled
    limite_y_max = max(todos) + 5 if todos else 10
    plt.ylim(bottom=0, top=limite_y_max)

    plt.title("Resumen diario de Prefect", fontsize=14)
    plt.xlabel("Hora", fontsize=12)
    plt.ylabel("Cantidad", fontsize=12)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    output_path = "reporte_diario.png"
    plt.savefig(output_path)
    print(f"📊 Gráfico generado desde Firebase y guardado en {output_path}")

    mensaje = "📊 Resumen diario de Prefect"
    enviar_imagen_telegram(output_path, mensaje=mensaje)
    os.remove(output_path)

    # 🔥 Limpiar colección resumenes (excepto test) al final del día
    borrar_resumenes_diarios()


if __name__ == "__main__":
    generar_grafico_resumen_firebase()
