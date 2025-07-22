import json
import os
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

firebase_app = None
db = None

def init_firebase():
    global firebase_app, db
    if firebase_app is None:
        cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        if not cred_json:
            raise Exception("FIREBASE_CREDENTIALS_JSON no está definido en el entorno")

        # Reparar formato si viene con comillas y saltos de línea escapados
        if cred_json.startswith('"') and cred_json.endswith('"'):
            cred_json = cred_json[1:-1]
        cred_dict = json.loads(cred_json)
        if "private_key" in cred_dict:
            cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")

        cred = credentials.Certificate(cred_dict)
        firebase_app = firebase_admin.initialize_app(cred)
        db = firestore.client()

    return db


def agregar_detalle_estado(failed, running, scheduled):
    db = init_firebase()
    hora_actual = datetime.now().strftime("%H:%M")

    data = {
        "hora": hora_actual,
        "failed": failed,
        "running": running,
        "scheduled": scheduled
    }

    try:
        doc_ref = db.collection("resumenes").document(hora_actual)
        doc_ref.set(data)  # ⬅ reemplaza si ya existe
        print(f"📝 Registro guardado para {hora_actual}")
    except Exception as e:
        print("❌ Error al registrar en Firestore:", str(e))
