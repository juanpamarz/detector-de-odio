from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline

app = FastAPI(title="Detector de Odio API")

# Cargar el modelo preentrenado especializado en español
detector = pipeline("text-classification", model="pysentimiento/robertuito-hate-speech")

class Mensaje(BaseModel):
    texto: str

@app.post("/analizar/")
async def analizar_texto(mensaje: Mensaje):
    resultado = detector(mensaje.texto)[0]
    
    # Determina si el texto es clasificado como Odio o Agresivo con una confianza relevante
    es_toxico = resultado['label'] in ['HATE', 'AGGRESSIVE'] and resultado['score'] > 0.60
    
    return {
        "texto_recibido": mensaje.texto,
        "etiqueta": resultado['label'],
        "confianza": round(resultado['score'], 4),
        "requiere_advertencia": es_toxico
    }