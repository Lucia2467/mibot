import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Load environment
load_dotenv()

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
WEBAPP_URL = os.environ.get('WEBAPP_URL', 'https://arcadepxc.pythonanywhere.com')
BOT_USERNAME = os.environ.get('BOT_USERNAME', 'ArcadePXCBot')
OFFICIAL_CHANNEL = os.environ.get('OFFICIAL_CHANNEL', '@ArcadePXC_Community')
SUPPORT_GROUP = os.environ.get('SUPPORT_GROUP', 'https://t.me/Soporte_ArcadePXC')

# Admin IDs
ADMIN_IDS = os.environ.get('ADMIN_IDS', '5515244003').split(',')

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Import database (try/except for standalone testing)
try:
    from database import (
        get_user, create_user, update_user,
        add_referral, get_referrals,
        increment_stat, get_stats,
        get_all_users_no_limit  # ✅ IMPORTAR LA FUNCIÓN SIN LÍMITE
    )
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("Database module not available")

# ============================================
# ✅ EJECUTAR MIGRACIONES AL INICIO
# Arregla el error: Columna desconocida 'activa'
# ============================================
try:
    from migrate_railway import run_migrations
    logger.info("🔧 Ejecutando migraciones de base de datos...")
    run_migrations()
    logger.info("✅ Migraciones completadas correctamente")
except Exception as e:
    logger.error(f"⚠️ Error al ejecutar migraciones (no crítico): {e}")

async def check_channel_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Verifica si el usuario es miembro del canal oficial"""
    try:
        # Remove @ from channel name if present
        channel = OFFICIAL_CHANNEL.replace('@', '')
        member = await context.bot.get_chat_member(f"@{channel}", user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking channel membership: {e}")
        # Return True on error to not block users
        return True

def get_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Genera el teclado del menú principal con WebApp"""
    webapp_url = f"{WEBAPP_URL}?user_id={user_id}"
    
    keyboard = [
        [InlineKeyboardButton(
            "🚀 Abrir ARCADE PXC", 
            web_app=WebAppInfo(url=webapp_url)
        )],
        [
            InlineKeyboardButton("👥 Mis Referidos", callback_data="my_referrals"),
            InlineKeyboardButton("📤 Compartir", callback_data="share_referral")
        ],
        [
            InlineKeyboardButton("📢 Canal Oficial", url=f"https://t.me/{OFFICIAL_CHANNEL.replace('@', '')}"),
            InlineKeyboardButton("💬 Soporte", url=SUPPORT_GROUP)
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)

def get_channel_join_keyboard() -> InlineKeyboardMarkup:
    """Genera el teclado para unirse al canal"""
    channel = OFFICIAL_CHANNEL.replace('@', '')
    
    keyboard = [
        [InlineKeyboardButton("📢 Unirse al Canal", url=f"https://t.me/{channel}")],
        [InlineKeyboardButton("✅ Ya me uní", callback_data="verify_channel")]
    ]
    
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - punto de entrada principal"""
    user = update.effective_user
    user_id = user.id
    username = user.username
    first_name = user.first_name
    
    # Extract referrer from args (format: ref_USERID)
    referrer_id = None
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith('ref_'):
            try:
                referrer_id = arg.replace('ref_', '')
                # Don't let users refer themselves
                if str(referrer_id) == str(user_id):
                    referrer_id = None
            except:
                pass
    
    # Create or update user in database
    if DB_AVAILABLE:
        existing_user = get_user(user_id)
        if existing_user:
            update_user(user_id, username=username, first_name=first_name)
        else:
            create_user(user_id, username=username, first_name=first_name, referrer_id=referrer_id)
        
        # Increment stats
        increment_stat('total_starts')
    
    # Check channel membership
    is_member = await check_channel_membership(user_id, context)
    
    if not is_member:
        # Show join channel prompt
        welcome_text = (
            f"👋 ¡Hola {first_name}!\n\n"
            f"🌟 Bienvenido a *ARCADE PXC*\n\n"
            f"Para acceder a todas las funciones, primero debes unirte a nuestro canal oficial:\n\n"
            f"📢 {OFFICIAL_CHANNEL}\n\n"
            f"Una vez que te unas, presiona el botón *Ya me uní* para continuar."
        )
        
        await update.message.reply_text(
            welcome_text,
            parse_mode='Markdown',
            reply_markup=get_channel_join_keyboard()
        )
        return
    
    # Show main menu
    welcome_text = (
        f"👋 ¡Hola {first_name}!\n\n"
        f"🌟 Bienvenido a *ARCADE PXC*\n\n"
        f"💰 Gana tokens minando\n"
        f"✅ Completa tareas para obtener recompensas\n"
        f"👥 Invita amigos y gana comisiones\n"
        f"💸 Retira tus ganancias en USDT o DOGE\n\n"
        f"Presiona el botón de abajo para comenzar:"
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=get_main_menu_keyboard(user_id)
    )

async def verify_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para verificar membresía del canal"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = user.id
    
    is_member = await check_channel_membership(user_id, context)
    
    if not is_member:
        await query.answer("❌ Aún no te has unido al canal. Por favor únete primero.", show_alert=True)
        return
    
    # Show main menu
    welcome_text = (
        f"✅ ¡Verificación exitosa!\n\n"
        f"🌟 Ya puedes acceder a *ARCADE PXC*\n\n"
        f"💰 Gana tokens minando\n"
        f"✅ Completa tareas para obtener recompensas\n"
        f"👥 Invita amigos y gana comisiones\n"
        f"💸 Retira tus ganancias en USDT o DOGE\n\n"
        f"Presiona el botón de abajo para comenzar:"
    )
    
    await query.edit_message_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=get_main_menu_keyboard(user_id)
    )

async def my_referrals_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para mostrar referidos"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not DB_AVAILABLE:
        await query.answer("Base de datos no disponible", show_alert=True)
        return
    
    referrals = get_referrals(user_id)
    
    if not referrals:
        text = (
            "👥 *Mis Referidos*\n\n"
            "Aún no tienes referidos.\n\n"
            "💡 Comparte tu link de referido para invitar amigos y ganar 1 PXC por cada uno que complete una tarea."
        )
    else:
        text = f"👥 *Mis Referidos* ({len(referrals)} total)\n\n"
        
        for i, ref in enumerate(referrals[:10], 1):
            name = ref.get('first_name') or ref.get('username') or ref.get('referred_id')
            status = "✅" if ref.get('validated') else "⏳"
            text += f"{i}. {name} {status}\n"
        
        if len(referrals) > 10:
            text += f"\n... y {len(referrals) - 10} más"
        
        text += "\n\n✅ = Validado | ⏳ = Pendiente"
    
    keyboard = [[InlineKeyboardButton("⬅️ Volver", callback_data="start")]]
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def share_referral_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para compartir link de referido"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    referral_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    
    text = (
        "📤 *Comparte tu Link de Referido*\n\n"
        f"🔗 Tu link personal:\n`{referral_link}`\n\n"
        "💰 Gana *1 PXC* por cada amigo que invite y complete al menos una tarea.\n\n"
        "📊 Además, recibes *5% de comisión* de todo lo que tus referidos minen."
    )
    
    keyboard = [
        [InlineKeyboardButton("📤 Compartir Link", 
                            switch_inline_query=f"¡Únete a ARCADE PXC y gana tokens! {referral_link}")],
        [InlineKeyboardButton("⬅️ Volver", callback_data="start")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para volver al menú principal"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = user.id
    first_name = user.first_name
    
    welcome_text = (
        f"👋 ¡Hola {first_name}!\n\n"
        f"🌟 Bienvenido a *ARCADE PXC*\n\n"
        f"💰 Gana tokens minando\n"
        f"✅ Completa tareas para obtener recompensas\n"
        f"👥 Invita amigos y gana comisiones\n"
        f"💸 Retira tus ganancias en USDT o DOGE\n\n"
        f"Presiona el botón de abajo para comenzar:"
    )
    
    await query.edit_message_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=get_main_menu_keyboard(user_id)
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /stats - solo para admins"""
    user_id = str(update.effective_user.id)
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ No tienes permiso para usar este comando.")
        return
    
    if not DB_AVAILABLE:
        await update.message.reply_text("❌ Base de datos no disponible.")
        return
    
    stats = get_stats()
    
    text = (
        "📊 *Estadísticas del Bot*\n\n"
        f"👥 Total de inicios: {stats.get('total_starts', 0)}\n"
        f"🔗 Total de referidos: {stats.get('total_referrals', 0)}\n"
        f"✅ Tareas completadas: {stats.get('total_tasks_completed', 0)}\n"
        f"💸 Retiros procesados: {stats.get('total_withdrawals', 0)}\n"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /broadcast - enviar mensaje a todos los usuarios (solo admins)"""
    user_id = str(update.effective_user.id)
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ No tienes permiso para usar este comando.")
        return
    
    if not DB_AVAILABLE:
        await update.message.reply_text("❌ Base de datos no disponible.")
        return
    
    # Verificar que haya un mensaje para enviar
    if not context.args:
        await update.message.reply_text(
            "📢 *Uso del comando broadcast:*\n\n"
            "`/broadcast Tu mensaje aquí`\n\n"
            "El mensaje será enviado a todos los usuarios registrados.\n\n"
            "*Tip:* Puedes usar Markdown y saltos de línea con \\n",
            parse_mode='Markdown'
        )
        return
    
    # Obtener el mensaje y procesar saltos de línea
    message = ' '.join(context.args)
    # Reemplazar \n literal por saltos de línea reales
    message = message.replace('\\n', '\n')
    
    # Confirmar antes de enviar
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirmar", callback_data=f"broadcast_confirm"),
            InlineKeyboardButton("❌ Cancelar", callback_data="broadcast_cancel")
        ]
    ]
    
    # Guardar el mensaje en el contexto del bot
    context.bot_data['pending_broadcast'] = message
    context.bot_data['broadcast_admin'] = user_id
    
    await update.message.reply_text(
        f"📢 *Vista previa del comunicado:*\n\n{message}\n\n"
        "¿Deseas enviar este mensaje a todos los usuarios?",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def broadcast_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para confirmar el broadcast - VERSIÓN CORREGIDA SIN LÍMITE"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    # Verificar permisos
    if user_id not in ADMIN_IDS:
        await query.answer("❌ No tienes permiso.", show_alert=True)
        return
    
    # Verificar que el admin que confirma sea el mismo que inició
    if user_id != context.bot_data.get('broadcast_admin'):
        await query.answer("❌ Solo quien inició el broadcast puede confirmarlo.", show_alert=True)
        return
    
    message = context.bot_data.get('pending_broadcast')
    
    if not message:
        await query.edit_message_text("❌ No hay mensaje pendiente para enviar.")
        return
    
    await query.edit_message_text("📤 Enviando comunicado a todos los usuarios...\n⏳ Por favor espera...")
    
    # ✅ SOLUCIÓN: Obtener TODOS los usuarios sin límite
    try:
        users = get_all_users_no_limit()
    except Exception as e:
        await query.edit_message_text(f"❌ Error al obtener usuarios: {e}")
        logger.error(f"Error getting users: {e}")
        return
    
    total_users = len(users)
    success_count = 0
    fail_count = 0
    blocked_count = 0
    
    logger.info(f"📊 Total usuarios en DB: {total_users}")
    
    # Enviar el mensaje a cada usuario
    for index, user in enumerate(users, 1):
        try:
            await context.bot.send_message(
                chat_id=user['user_id'],
                text=message,
                parse_mode='Markdown'
            )
            success_count += 1
            
            # Actualizar progreso cada 100 mensajes
            if index % 100 == 0:
                logger.info(f"📊 Progreso: {index}/{total_users}")
                try:
                    await query.edit_message_text(
                        f"📤 Enviando comunicado...\n\n"
                        f"📊 Progreso: {index}/{total_users}\n"
                        f"✅ Enviados: {success_count}\n"
                        f"🚫 Bloqueados: {blocked_count}\n"
                        f"❌ Fallidos: {fail_count}"
                    )
                except:
                    pass  # Ignorar errores de edición de mensaje
            
            # Pequeña pausa para evitar límites de rate (25 msg/segundo)
            import asyncio
            await asyncio.sleep(0.04)
            
        except Exception as e:
            error_msg = str(e).lower()
            if 'forbidden' in error_msg or 'blocked' in error_msg:
                blocked_count += 1
                logger.warning(f"User {user['user_id']} blocked the bot")
            else:
                fail_count += 1
                logger.error(f"Error sending to {user['user_id']}: {e}")
    
    # Limpiar el contexto
    context.bot_data.pop('pending_broadcast', None)
    context.bot_data.pop('broadcast_admin', None)
    
    # Reportar resultados
    result_text = (
        "✅ *Comunicado enviado*\n\n"
        f"📊 Estadísticas:\n"
        f"👥 Total en DB: {total_users}\n"
        f"✅ Enviados: {success_count}\n"
        f"🚫 Bloquearon bot: {blocked_count}\n"
        f"❌ Fallidos: {fail_count}"
    )
    
    await query.edit_message_text(result_text, parse_mode='Markdown')

async def broadcast_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para cancelar el broadcast"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    if user_id not in ADMIN_IDS:
        await query.answer("❌ No tienes permiso.", show_alert=True)
        return
    
    # Limpiar el contexto
    context.bot_data.pop('pending_broadcast', None)
    context.bot_data.pop('broadcast_admin', None)
    
    await query.edit_message_text("❌ Comunicado cancelado.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help"""
    user_id = str(update.effective_user.id)
    
    text = (
        "ℹ️ *Ayuda de ARCADE PXC*\n\n"
        "*Comandos disponibles:*\n"
        "/start - Iniciar el bot\n"
        "/help - Ver esta ayuda\n"
    )
    
    # Agregar comandos de admin si es admin
    if user_id in ADMIN_IDS:
        text += (
            "\n*Comandos de Admin:*\n"
            "/stats - Ver estadísticas del bot\n"
            "/broadcast - Enviar comunicado a todos\n"
        )
    
    text += (
        "\n*¿Cómo funciona?*\n"
        "1️⃣ Abre la aplicación con el botón\n"
        "2️⃣ Mina tokens automáticamente\n"
        "3️⃣ Completa tareas para ganar más\n"
        "4️⃣ Invita amigos y gana comisiones\n"
        "5️⃣ Retira en USDT o DOGE\n\n"
        f"📢 Canal: {OFFICIAL_CHANNEL}\n"
        f"💬 Soporte: {SUPPORT_GROUP}"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja errores"""
    logger.error(f"Error: {context.error}")

def main():
    """Función principal"""
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN not configured")
        print("Please set BOT_TOKEN in .env file")
        return
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(verify_channel_callback, pattern="^verify_channel$"))
    application.add_handler(CallbackQueryHandler(my_referrals_callback, pattern="^my_referrals$"))
    application.add_handler(CallbackQueryHandler(share_referral_callback, pattern="^share_referral$"))
    application.add_handler(CallbackQueryHandler(start_callback, pattern="^start$"))
    application.add_handler(CallbackQueryHandler(broadcast_confirm_callback, pattern="^broadcast_confirm$"))
    application.add_handler(CallbackQueryHandler(broadcast_cancel_callback, pattern="^broadcast_cancel$"))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    print("🤖 ARCADE PXC starting...")
    print(f"📢 Channel: {OFFICIAL_CHANNEL}")
    print(f"🌐 WebApp: {WEBAPP_URL}")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
