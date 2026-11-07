import os
import httpx
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, filters, ContextTypes

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_IA_URL = os.getenv("API_IA_URL", "http://127.0.0.1:8000/analizar/")

# Máximo número de advertencias antes de banear del grupo
MAX_ADVERTENCIAS = 50

async def analizar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    texto_usuario = update.message.text
    usuario = update.message.from_user
    chat_id = update.effective_chat.id

    # Consultar a la API de IA
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            respuesta = await client.post(API_IA_URL, json={"texto": texto_usuario})
            datos = respuesta.json()
    except Exception as e:
        print(f"⚠️ Error al conectar con la API de IA: {type(e).__name__} - {e}")
        return

 # -------------------------------------------------------------
    # CASO 1: DETECCIÓN DE RIESGO DE VIDA / AUTOLESIÓN (PRIVADO)
    # -------------------------------------------------------------
    if datos.get("es_crisis", False):
        # 1. Borramos el mensaje del grupo para proteger al usuario y al chat
        try:
            await update.message.delete()
        except Exception as e:
            print(f"Error al borrar mensaje de crisis: {e}")

        mensaje_apoyo_privado = (
            f"💙 Hola {usuario.first_name}, leímos tu mensaje en el grupo y nos preocupamos por ti.\n\n"
            f"Queremos que sepas que **no estás solo/a** y que hay personas dispuestas a escucharte sin juzgarte.\n\n"
            f"📞 **Líneas de Atención Gratuita 24/7:**\n"
            f"• **Línea de la Vida (México):** 800 911 2000\n"
            f"• **Emergencias:** 911\n\n"
            f"Por favor, ponte en contacto con ellos o habla con alguien de confianza."
        )
        
        # 2. Intentamos enviarle un mensaje PRIVADO directo al usuario
        try:
            await context.bot.send_message(
                chat_id=usuario.id, 
                text=mensaje_apoyo_privado, 
                parse_mode="Markdown"
            )
        except Exception:
            # Si el usuario no ha iniciado chat privado con el bot previamente, enviamos un aviso discreto en el grupo
            await context.bot.send_message(
                chat_id=chat_id, 
                text=f"💙 @{usuario.username or usuario.first_name}, te hemos eliminado el mensaje por tu tranquilidad y te enviamos un mensaje de apoyo. No estás solo/a."
            )
        return

    # -------------------------------------------------------------
    # CASO 2: MENSAJE TÓXICO / LENGUAJE DE ODIO
    # -------------------------------------------------------------
    if datos.get("requiere_advertencia", False):
        # 1. Borrar el mensaje ofensivo del grupo
        try:
            await update.message.delete()
        except Exception as e:
            print(f"Error al borrar mensaje: {e}")

        # 2. Incrementar el contador de faltas del usuario
        user_key = f"warnings_{usuario.id}"
        faltas_actuales = context.chat_data.get(user_key, 0) + 1
        context.chat_data[user_key] = faltas_actuales

        # Si supera las 15 faltas -> Expulsar del grupo
        if faltas_actuales >= MAX_ADVERTENCIAS:
            try:
                await context.bot.ban_chat_member(chat_id=chat_id, user_id=usuario.id)
                await context.bot.send_message(
                    chat_id=chat_id, 
                    text=f"🚫 El usuario @{usuario.username or usuario.first_name} ha sido expulsado del grupo tras acumular {MAX_ADVERTENCIAS} advertencias por lenguaje ofensivo."
                )
            except Exception as e:
                print(f"Error al expulsar usuario: {e}")
            return

        # 3. Guardar el contenido temporalmente por si decide republicarlo
        id_unico = str(update.message.message_id)
        context.chat_data[id_unico] = {
            'texto': texto_usuario,
            'usuario_nombre': usuario.first_name,
            'usuario_id': usuario.id
        }

        # Botones de confirmación
        teclado = [
            [
                InlineKeyboardButton("❌ Retirar mensaje", callback_data=f"cancel_{id_unico}"),
                InlineKeyboardButton("⚠️ Publicar de todos modos", callback_data=f"send_{id_unico}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(teclado)

        # Mensaje de reflexión empático
        mensaje_reflexivo = (
            f"🌱 **Hola @{usuario.username or usuario.first_name}**, hemos eliminado tu mensaje porque consideramos "
            f"que puede resultar hiriente o generar un ambiente hostil.\n\n"
            f"Te invitamos a la reflexión: *No envíes mensajes que no te gustaría recibir.* "
            f"Fomentemos un grupo respetuoso para todos.\n\n"
            f"⚠️ *Advertencia ({faltas_actuales}/{MAX_ADVERTENCIAS}):* Si acumulas {MAX_ADVERTENCIAS} faltas, serás expulsado automáticamente."
        )

        await context.bot.send_message(
            chat_id=chat_id, 
            text=mensaje_reflexivo, 
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def manejar_botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    accion, id_unico = query.data.split('_')
    datos_mensaje = context.chat_data.get(id_unico)

    if not datos_mensaje:
        await query.answer("El tiempo para esta interacción ha expirado.", show_alert=True)
        return

    # REQUERIMIENTO PRIVADO: Si alguien que NO es el creador del mensaje presiona el botón
    if query.from_user.id != datos_mensaje['usuario_id']:
        await query.answer("❌ Esta acción solo la puede realizar la persona que escribió el mensaje.", show_alert=True)
        return

    await query.answer()

    if accion == "cancel":
        await query.delete_message()
        del context.chat_data[id_unico]

    elif accion == "send":
        texto_final = f"💬 Mensaje de @{datos_mensaje['usuario_nombre']}:\n\n{datos_mensaje['texto']}"
        await query.edit_message_text(text=texto_final)
        del context.chat_data[id_unico]

def main():
    if not TOKEN:
        print("Error: No se encontró TELEGRAM_BOT_TOKEN en el archivo .env")
        return

    app = Application.builder().token(TOKEN).read_timeout(30).write_timeout(30).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, analizar_mensaje))
    app.add_handler(CallbackQueryHandler(manejar_botones))
    print("\n🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖")
    print("Bot listo y trabajando")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()