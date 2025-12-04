import logging
from telebot import TeleBot, types
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
import config
import database
import google.generativeai as genai

# ------------------ КОНСТАНТЫ ------------------
GEMINI_API_KEY = "AIzaSyCYAI1wsZD7DSjJf3HPA0BQHfiLfxlLDEs"

# ------------------ ЛОГИРОВАНИЕ ------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)

# ------------------ FSM ХРАНИЛИЩЕ ------------------
state_storage = StateMemoryStorage()
bot = TeleBot(config.BOT_TOKEN, state_storage=state_storage)

# ------------------ ИНИЦИАЛИЗАЦИЯ БД ------------------
try:
    database.init_db()
    logging.info("База данных успешно инициализирована.")
except Exception as e:
    logging.error(f"Ошибка при инициализации БД: {e}")


# ------------------ СОСТОЯНИЯ ------------------
class UserStates(StatesGroup):
    choosing_course = State()
    choosing_topic = State()
    admin_choosing_action = State()
    admin_entering_course = State()
    admin_entering_topic = State()
    admin_waiting_file = State()
    admin_choosing_file_type = State()
    gemini_chat = State()


# ------------------ ПРОВЕРКА АДМИНА ------------------
def is_admin(user_id):
    try:
        return int(user_id) in config.ADMIN_IDS
    except Exception:
        return False


# ------------------ ОБЩИЕ ФУНКЦИИ ------------------
def safe_delete_state(user_id, chat_id):
    """Безопасное удаление состояния"""
    try:
        bot.delete_state(user_id, chat_id)
    except Exception:
        pass


def go_home(chat_id, user_id, text="Главное меню:"):
    """Возврат в главное меню"""
    try:
        safe_delete_state(user_id, chat_id)
        bot.send_message(chat_id, text, reply_markup=create_main_menu(is_admin(user_id)))
    except Exception as e:
        logging.error(f"Ошибка при возврате в главное меню: {e}")


def create_main_menu(is_admin_user=False):
    """Создание клавиатуры главного меню"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = ["📚 Лекции", "❓ Помощь", "ℹ️ О боте", "🤖 Чат с нейросетью"]
    if is_admin_user:
        buttons = ["📚 Лекции", "➕ Добавить лекцию", "📁 Добавить файл", "📊 База данных", "❓ Помощь",
                   "🤖 Чат с нейросетью"]

    # Разбиваем кнопки на ряды для лучшего отображения
    for i in range(0, len(buttons), 2):
        row = buttons[i:i + 2]
        markup.add(*[types.KeyboardButton(btn) for btn in row])

    return markup


def create_back_button():
    """Создание кнопки Назад"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 Назад"))
    return markup


def show_welcome_message(chat_id, user_id):
    """Показ приветственного сообщения"""
    try:
        is_admin_user = is_admin(user_id)
        welcome_text = "👋 Добро пожаловать в Bonch inform Bot!"
        if is_admin_user:
            welcome_text += "\n👨‍💼 Режим администратора"
        bot.send_message(chat_id, welcome_text, reply_markup=create_main_menu(is_admin_user))
        safe_delete_state(user_id, chat_id)
    except Exception as e:
        logging.error(f"Ошибка при отправке приветственного сообщения: {e}")


def is_back_command(message):
    """Проверка на команду Назад"""
    return message.text == "🔙 Назад"


def handle_back_command(message):
    """Обработка команды Назад"""
    go_home(message.chat.id, message.from_user.id)


# ------------------ ЧАТ С GEMINI ------------------
user_gemini_states = {}


def start_gemini_chat(message):
    """Запуск чата с Gemini"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_gemini_states[user_id] = True
    bot.set_state(user_id, UserStates.gemini_chat, chat_id)

    bot.send_message(chat_id,
                     "🤖 Вы вошли в чат с нейросетью Gemini 2.5 Flash.\n"
                     "Отправьте сообщение или нажмите 🔙 Назад для выхода.",
                     reply_markup=create_back_button())


def handle_gemini_message(message):
    """Обработка сообщений в чате с Gemini"""
    chat_id = message.chat.id
    user_id = message.from_user.id

    if is_back_command(message):
        user_gemini_states.pop(user_id, None)
        safe_delete_state(user_id, chat_id)
        go_home(chat_id, user_id)
        return

    if not user_gemini_states.get(user_id):
        return

    user_input = message.text
    if not user_input or user_input.strip() == "":
        bot.send_message(chat_id, "❌ Сообщение не может быть пустым.")
        return

    try:
        # Показываем индикатор набора
        bot.send_chat_action(chat_id, 'typing')

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(user_input)

        gemini_text = getattr(response, "output_text", None) or getattr(response, "text", "")
        gemini_text = gemini_text.strip() or "❌ Нет ответа от нейросети"

        # Ограничение длины сообщения для Telegram
        if len(gemini_text) > 4000:
            gemini_text = gemini_text[:4000] + "..."

        gemini_text = gemini_text.replace("**", "*")
        bot.send_message(chat_id, gemini_text, parse_mode=None)

    except Exception as e:
        logging.error(f"Ошибка при общении с Gemini: {e}")
        bot.send_message(chat_id, "⚠️ Ошибка при отправке запроса к нейросети. Попробуйте позже.")

