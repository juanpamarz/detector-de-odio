from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline

app = FastAPI(title="Detector de Odio API")

# Cargar el modelo preentrenado de pysentimiento
detector = pipeline("text-classification", model="pysentimiento/robertuito-hate-speech")

class Mensaje(BaseModel):
    texto: str

@app.post("/analizar/")
async def analizar_texto(mensaje: Mensaje):
    resultado = detector(mensaje.texto)[0]
    
    # Normalizamos la etiqueta recibida a minúsculas para evitar fallos
    etiqueta = resultado['label'].lower()
    score = resultado['score']
    
    # Imprimir en consola para monitorear cada petición
    print(f"📩 Texto: '{mensaje.texto}' | Etiqueta detectada: '{etiqueta}' | Score: {score:.4f}")
    
    # Lista de etiquetas reales que usa pysentimiento: 'hateful', 'targeted', 'aggressive'
    etiquetas_toxicas = ['hateful', 'targeted', 'aggressive']
    
    # Umbral flexible: activa advertencia si coincide la etiqueta Y supera 0.05 (5% de score)
    # o si se trata de un mensaje muy corto/directo
    es_toxico = etiqueta in etiquetas_toxicas and score > 0.05
    
    return {
        "texto_recibido": mensaje.texto,
        "etiqueta": etiqueta,
        "confianza": round(score, 4),
        "requiere_advertencia": es_toxico
    }