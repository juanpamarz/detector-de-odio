import sqlite3
from datetime import datetime

DB_NAME = "moderacion_bot.db"

def init_db():
    """Inicializa la base de datos de auditoría."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registros_moderacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT,
            usuario_id INTEGER,
            usuario_nombre TEXT,
            mensaje_texto TEXT,
            categoria TEXT,
            es_crisis BOOLEAN,
            requiere_advertencia BOOLEAN
        )
    ''')
    conn.commit()
    conn.close()

def registrar_incidente(usuario_id: int, usuario_nombre: str, mensaje_texto: str, categoria: str, es_crisis: bool, requiere_advertencia: bool):
    """Guarda un incidente analizado en la base de datos."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO registros_moderacion (fecha_hora, usuario_id, usuario_nombre, mensaje_texto, categoria, es_crisis, requiere_advertencia)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), usuario_id, usuario_nombre, mensaje_texto, categoria, es_crisis, requiere_advertencia))
    conn.commit()
    conn.close()