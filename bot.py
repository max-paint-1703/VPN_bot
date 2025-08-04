import os
import shutil
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler
)

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')

# Пути к директориям
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AVAILABLE_DIR = os.path.join(BASE_DIR, 'configs', 'available')
USED_DIR = os.path.join(BASE_DIR, 'configs', 'used')

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Словарь для хранения ожидающих запросов {user_id: config_file}
pending_requests = {}

def check_configs():
    """Проверка наличия доступных конфигов"""
    if not os.path.exists(AVAILABLE_DIR):
        os.makedirs(AVAILABLE_DIR)
    if not os.path.exists(USED_DIR):
        os.makedirs(USED_DIR)
    
    return [f for f in os.listdir(AVAILABLE_DIR) if f.endswith('.conf')]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""
    user = update.message.from_user
    await update.message.reply_text(
        f"Привет, {user.first_name}!\n"
        "Используй команду /get_config чтобы запросить VPN-конфиг"
    )

async def get_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка запроса конфига"""
    user = update.message.from_user
    configs = check_configs()
    
    if not configs:
        await update.message.reply_text(
            "⚠️ Извините, все ключи временно закончились.\n"
            "Администратор уже уведомлен, попробуйте позже."
        )
        await notify_admin(context, "⚠️ ВНИМАНИЕ! Закончились доступные конфиги!")
        return
    
    # Сохраняем запрос
    config_file = configs[0]
    pending_requests[user.id] = config_file
    
    # Формируем сообщение для администратора
    username = f"@{user.username}" if user.username else "нет username"
    request_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    admin_message = (
        f"🆕 Новый запрос конфига:\n"
        f"👤 Имя: {user.full_name}\n"
        f"📌 Username: {username}\n"
        f"🆔 ID: {user.id}\n"
        f"🕒 Время: {request_time}\n"
        f"📁 Файл: {config_file}"
    )
    
    # Кнопки для администратора
    keyboard = [
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton("❌ Отказать", callback_data=f"reject_{user.id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем администратору
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=admin_message,
        reply_markup=reply_markup
    )
    
    # Сообщение пользователю
    await update.message.reply_text(
        "✅ Ваш запрос отправлен администратору на проверку. "
        "Ожидайте решения в течение нескольких минут."
    )
    logger.info(f"Запрос от пользователя {user.id} отправлен на модерацию")

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действий администратора"""
    query = update.callback_query
    await query.answer()
    
    action, user_id = query.data.split('_')
    user_id = int(user_id)
    config_file = pending_requests.get(user_id)
    
    if not config_file:
        await query.edit_message_text("⚠️ Ошибка: запрос не найден или уже обработан")
        return
    
    if action == "approve":
        # Выдаем конфиг пользователю
        src_path = os.path.join(AVAILABLE_DIR, config_file)
        dest_path = os.path.join(USED_DIR, config_file)
        
        try:
            await context.bot.send_document(
                chat_id=user_id,
                document=open(src_path, 'rb'),
                caption=f"Ваш конфиг: {config_file}\n"
                        "Сохраните этот файл и используйте в WireGuard"
            )
            # Перемещаем в использованные
            shutil.move(src_path, dest_path)
            
            # Уведомления
            await query.edit_message_text(f"✅ Конфиг {config_file} выдан пользователю ID: {user_id}")
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"Ключ {config_file} выдан пользователю ID: {user_id}"
            )
            logger.info(f"Конфиг {config_file} выдан пользователю {user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка выдачи конфига: {e}")
            await query.edit_message_text(f"🚫 Ошибка выдачи конфига: {e}")
            await context.bot.send_message(
                chat_id=user_id,
                text="⚠️ Произошла ошибка при обработке вашего запроса. Попробуйте позже."
            )
    
    elif action == "reject":
        # Отказываем в выдаче
        del pending_requests[user_id]
        
        await query.edit_message_text(f"❌ Запрос пользователя ID: {user_id} отклонён")
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"Отказано пользователю ID: {user_id}"
        )
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Ваш запрос на получение конфига отклонён администратором."
        )
        logger.info(f"Запрос пользователя {user_id} отклонён")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    await update.message.reply_text(
        "Используйте команду /get_config для запроса конфига"
    )

async def notify_admin(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Уведомление администратора"""
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=message
        )
        logger.info("Администратор уведомлен")
    except Exception as e:
        logger.error(f"Ошибка уведомления администратора: {e}")

def main():
    """Запуск бота"""
    application = Application.builder().token(TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("get_config", get_config))
    application.add_handler(CallbackQueryHandler(handle_admin_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Проверка начальных условий
    configs = check_configs()
    if not configs:
        logger.warning("На старте нет доступных конфигов!")
    
    # Запуск бота
    application.run_polling()
    logger.info("Бот запущен")

if __name__ == "__main__":
    main()