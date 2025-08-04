import os
import shutil
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
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
        "Используй команду /get_config чтобы получить VPN-конфиг"
    )

async def get_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдача конфигурационного файла"""
    configs = check_configs()
    
    if not configs:
        await update.message.reply_text(
            "⚠️ Извините, все ключи временно закончились.\n"
            "Администратор уже уведомлен, попробуйте позже."
        )
        await notify_admin(context, "⚠️ ВНИМАНИЕ! Закончились доступные конфиги!")
        return
    
    # Выбираем первый доступный конфиг
    config_file = configs[0]
    src_path = os.path.join(AVAILABLE_DIR, config_file)
    dest_path = os.path.join(USED_DIR, config_file)
    
    # Отправляем файл пользователю
    try:
        await update.message.reply_document(
            document=open(src_path, 'rb'),
            caption=f"Ваш конфиг: {config_file}\n"
                    "Сохраните этот файл и используйте в WireGuard"
        )
        # Перемещаем в использованные
        shutil.move(src_path, dest_path)
        logger.info(f"Выдан конфиг: {config_file} пользователю {update.message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка отправки файла: {e}")
        await update.message.reply_text("🚫 Произошла ошибка при отправке файла")

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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    await update.message.reply_text(
        "Используйте команду /get_config для получения конфига"
    )

def main():
    """Запуск бота"""
    application = Application.builder().token(TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("get_config", get_config))
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