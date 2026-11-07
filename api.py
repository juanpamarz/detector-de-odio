import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from groq import Groq
from transformers import pipeline
from database import init_db, registrar_incidente

# 1. Cargar variables de entorno e inicializar base de datos
load_dotenv()
init_db()

app = FastAPI(title="Detector de Odio e Inteligencia API con Groq")

# 2. Inicialización del cliente de Groq
groq_key = os.getenv("GROQ_API_KEY")
client_groq = Groq(api_key=groq_key) if groq_key else None

# 3. Cargar el modelo local de Hugging Face como respaldo definitivo
print("⏳ Cargando modelo local de Hugging Face (RoBERTuito)...")
try:
    clasificador_local = pipeline("text-classification", model="pysentimiento/robertuito-hate-speech")
    print("✅ Modelo local cargado correctamente.")
except Exception as err:
    print(f"⚠️ No se pudo cargar el modelo local: {err}")
    clasificador_local = None

# Modelo de datos que recibe la API desde Telegram
class Mensaje(BaseModel):
    texto: str
    usuario_id: int = 0
    usuario_nombre: str = "Anónimo"

def evaluar_modelo_local(texto: str):
    """Respaldo rápido con el modelo local de Hugging Face cuando falla la API externa."""
    texto_lower = texto.lower()
    
    # 1. Evaluación de Crisis
    palabras_crisis = ["suicid", "matarm", "quitarme la vida", "no quiero vivir", "acabar con todo", "morir", "desaparecer"]
    if any(p in texto_lower for p in palabras_crisis):
        return {"categoria": "CRISIS", "requiere_advertencia": False, "es_crisis": True}

    # 2. Evaluación de Toxicidad por palabras clave
    palabras_toxicas = ["mierda", "inutil", "inútil", "estupido", "estúpido", "pendejo", "imbecil", "imbécil", "perra", "puta"]
    if any(p in texto_lower for p in palabras_toxicas):
        return {"categoria": "TOXICO", "requiere_advertencia": True, "es_crisis": False}

    if clasificador_local:
        try:
            res = clasificador_local(texto)[0]
            label = str(res['label']).lower()
            score = res['score']
            if label in ['hateful', 'targeted', 'profanity', 'aggressive'] and score > 0.20:
                return {"categoria": "TOXICO", "requiere_advertencia": True, "es_crisis": False}
        except Exception as e:
            print(f"Error evaluando localmente: {e}")

    return {"categoria": "NORMAL", "requiere_advertencia": False, "es_crisis": False}

@app.post("/analizar/")
async def analizar_texto(mensaje: Mensaje):
    prompt = f"""
    Analiza el siguiente mensaje enviado a un chat grupal:
    "{mensaje.texto}"

    Debes clasificarlo en una de estas categorías:
    1. "CRISIS": El usuario expresa ideación suicida, deseo de hacerse daño o atentar contra su vida.
    2. "TOXICO": El mensaje contiene lenguaje de odio, agresión grave, acoso o insultos directos.
    3. "NORMAL": Mensaje cotidiano, seguro y no ofensivo.

    Responde ÚNICAMENTE un formato JSON estricto con esta estructura:
    {{
        "categoria": "CRISIS" | "TOXICO" | "NORMAL",
        "requiere_advertencia": true/false,
        "es_crisis": true/false
    }}
    """
    
    datos = None

    # Intentar análisis con Groq
    if client_groq:
        try:
            chat_completion = client_groq.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
                response_format={"type": "json_object"}
            )
            res_text = chat_completion.choices[0].message.content
            datos = json.loads(res_text)
            print(f"✅ Respuesta exitosa de GROQ: {datos}")
        except Exception as e:
            print(f"⚠️ Groq falló o no respondió: {e}")

    # Fallback local si Groq no respondió
    if not datos:
        print("🔄 Derivando al análisis local...")
        datos = evaluar_modelo_local(mensaje.texto)

    # GUARDAR EN LA BASE DE DATOS (SQLite)
    try:
        registrar_incidente(
            usuario_id=mensaje.usuario_id,
            usuario_nombre=mensaje.usuario_nombre,
            mensaje_texto=mensaje.texto,
            categoria=datos.get("categoria", "NORMAL"),
            es_crisis=datos.get("es_crisis", False),
            requiere_advertencia=datos.get("requiere_advertencia", False)
        )
        print("💾 Incidente guardado en la base de datos.")
    except Exception as db_err:
        print(f"⚠️ Error al guardar en DB: {db_err}")

    return datos