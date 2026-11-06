import os
import httpx
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Cargar variables secretas desde .env
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_IA_URL = os.getenv("API_IA_URL", "http://127.0.0.1:8000/analizar/")

async def analizar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    texto_usuario = update.message.text
    usuario = update.message.from_user
    
    # Enviar el mensaje a la API de IA de forma asíncrona con httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            respuesta = await client.post(API_IA_URL, json={"texto": texto_usuario})
            datos = respuesta.json()
    except Exception as e:
        print(f"Error al conectar con la API de IA: {e}")
        return

    # Si la IA determina que requiere advertencia
    if datos.get("requiere_advertencia", False):
        try:
            # Borrar el mensaje tóxico del grupo
            await update.message.delete()
        except Exception as e:
            print(f"No se pudo borrar el mensaje (¿Faltan permisos de Administrador?): {e}")
            return
        
        # Guardar en memoria el mensaje original
        id_unico = str(update.message.message_id)
        context.chat_data[id_unico] = {
            'texto': texto_usuario,
            'usuario_nombre': usuario.first_name,
            'usuario_id': usuario.id
        }
        
        # Crear los botones de confirmación
        teclado = [
            [
                InlineKeyboardButton("❌ Cancelar", callback_data=f"cancel_{id_unico}"),
                InlineKeyboardButton("⚠️ Aceptar y Enviar", callback_data=f"send_{id_unico}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(teclado)
        
        # Enviar mensaje de advertencia
        advertencia = (f"⚠️ @{usuario.username or usuario.first_name}, tu mensaje contiene posible "
                       f"lenguaje ofensivo o de odio.\n\n"
                       f"¿Deseas publicarlo bajo tu propia responsabilidad?")
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=advertencia, 
            reply_markup=reply_markup
        )

async def manejar_botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    accion, id_unico = query.data.split('_')
    datos_mensaje = context.chat_data.get(id_unico)
    
    if not datos_mensaje:
        await query.edit_message_text(text="El tiempo para esta acción ha expirado.")
        return
        
    # Verificar que solo quien escribió el mensaje pueda presionar los botones
    if query.from_user.id != datos_mensaje['usuario_id']:
        return

    if accion == "cancel":
        await query.edit_message_text(text=f"✅ {datos_mensaje['usuario_nombre']} retiró el mensaje.")
        del context.chat_data[id_unico]
        
    elif accion == "send":
        texto_final = f"Mensaje de {datos_mensaje['usuario_nombre']} (Bajo advertencia):\n\n{datos_mensaje['texto']}"
        await query.edit_message_text(text=texto_final)
        del context.chat_data[id_unico]

def main():
    if not TOKEN:
        print("Error: No se encontró TELEGRAM_BOT_TOKEN en el archivo .env")
        return

    # Aumentar timeouts para evitar NetworkError por micro-cortes
    app = Application.builder().token(TOKEN).read_timeout(30).write_timeout(30).build()
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, analizar_mensaje))
    app.add_handler(CallbackQueryHandler(manejar_botones))
    
    print("🤖 Bot listo y escuchando en Telegram...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()