import logging
import re
from telebot import types
from common_functions import (
    bot, show_welcome_message, go_home, create_main_menu,
    is_admin, start_gemini_chat, handle_gemini_message,
    user_gemini_states, is_back_command, handle_back_command,
    UserStates, safe_delete_state
)
import admin_functions
import database

# ------------------ ЛОГИРОВАНИЕ ------------------
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')


# ------------------ СТАРТ ------------------
@bot.message_handler(commands=['start'])
def start_handler(message):
    logging.info(f"/start от {message.from_user.id}")
    show_welcome_message(message.chat.id, message.from_user.id)


# ------------------ КНОПКА "ЛЕКЦИИ" ------------------
@bot.message_handler(func=lambda m: m.text == "📚 Лекции")
def handle_lectures(message):
    logging.info(f"Выбор 'Лекции' от {message.from_user.id}")
    try:
        courses = database.get_all_courses()
        if not courses:
            bot.send_message(message.chat.id, "📭 Нет доступных курсов.")
            return

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for course in courses:
            markup.add(types.KeyboardButton(f"📘 Курс {course}"))
        markup.add(types.KeyboardButton("🔙 Назад"))

        bot.send_message(message.chat.id, "Выберите курс:", reply_markup=markup)
    except Exception as e:
        logging.exception(f"Ошибка при получении курсов: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка при загрузке курсов.")


# ------------------ ВЫБОР КУРСА ------------------
@bot.message_handler(func=lambda m: m.text.startswith("📘 Курс "))
def handle_course_selection(message):
    logging.info(f"Выбор курса: {message.text} от {message.from_user.id}")
    try:
        match = re.match(r"📘 Курс (\d+)", message.text)
        if not match:
            bot.send_message(message.chat.id, "❌ Неверный курс.")
            return

        course = int(match.group(1))
        topics = database.get_topics_by_course(course)
        logging.info(f"Темы для курса {course}: {topics}")

        if not topics:
            bot.send_message(message.chat.id, "📭 Нет лекций для этого курса.")
            return

        markup = types.InlineKeyboardMarkup()
        for topic in topics:
            cb_data = f"show_lecture_{course}_{topic.replace(' ', '~')}"
            markup.add(types.InlineKeyboardButton(text=topic, callback_data=cb_data))

        bot.send_message(message.chat.id, f"📘 Лекции курса {course}:", reply_markup=markup)
    except Exception as e:
        logging.exception(f"Ошибка при отображении лекций: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка при загрузке лекций.")


# ------------------ ПОКАЗ ЛЕКЦИИ ------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("show_lecture_"))
def show_lecture(call):
    logging.info(f"Callback show_lecture: {call.data} от {call.from_user.id}")
    try:
        match = re.match(r"show_lecture_(\d+)_(.+)", call.data)
        if not match:
            logging.warning(f"Неверный callback show_lecture: {call.data}")
            bot.answer_callback_query(call.id, "❌ Ошибка данных.")
            return

        course = int(match.group(1))
        topic = match.group(2).replace("~", " ")
        lecture = database.get_lecture(course, topic)

        if not lecture:
            bot.answer_callback_query(call.id, "❌ Лекция не найдена.")
            return

        # Формируем текст сообщения
        text = f"📖 <b>{topic}</b>\nКурс: {course}\n\n"
        files_info = []

        file_availability = [
            ("🎧 Аудиофайл доступен", lecture[3]),
            ("📄 Документ доступен", lecture[4]),
            ("📊 Презентация доступна", lecture[5]),
            ("🖼 Фото доступно", lecture[6])
        ]

        for file_text, file_id in file_availability:
            if file_id:
                files_info.append(file_text)

        text += "\n".join(files_info) if files_info else "❌ Нет файлов для этой лекции."

        # Создаем кнопки для файлов
        markup = types.InlineKeyboardMarkup()
        buttons_data = [
            ("🎧 Аудио", "audio", lecture[3]),
            ("📄 Документ", "document", lecture[4]),
            ("📊 Презентация", "presentation", lecture[5]),
            ("🖼 Фото", "view_photo", lecture[6])
        ]

        for btn_text, file_type, file_id in buttons_data:
            if file_id:
                callback_data = f"get_file_{file_type}_{course}_{topic.replace(' ', '~')}"
                markup.add(types.InlineKeyboardButton(btn_text, callback_data=callback_data))

        # Кнопка удаления для админа
        if is_admin(call.from_user.id):
            markup.add(types.InlineKeyboardButton(
                "🗑 Удалить лекцию",
                callback_data=f"delete_lecture_{course}_{topic.replace(' ', '~')}"
            ))

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=markup
        )

    except Exception as e:
        logging.exception(f"Ошибка при отображении лекции: {e}")
        bot.answer_callback_query(call.id, "⚠️ Ошибка при открытии лекции.")


# ------------------ ПОЛУЧЕНИЕ ФАЙЛОВ ------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("get_file_"))
def handle_get_file(call):
    logging.info(f"Callback get_file: {call.data} от {call.from_user.id}")
    try:
        match = re.match(r"get_file_(audio|document|presentation)_(\d+)_(.+)", call.data)
        if not match:
            logging.warning(f"Неверный callback get_file: {call.data}")
            bot.answer_callback_query(call.id, "❌ Неверные данные.")
            return

        file_type, course, topic = match.groups()
        course = int(course)
        topic = topic.replace("~", " ")

        lecture = database.get_lecture(course, topic)
        if not lecture:
            bot.answer_callback_query(call.id, "❌ Лекция не найдена.")
            return

        index_map = {"audio": 3, "document": 4, "presentation": 5}
        file_id = lecture[index_map[file_type]]

        if not file_id:
            bot.answer_callback_query(call.id, "❌ Файл отсутствует.")
            return

        # Отправка файла
        if file_type == "audio":
            bot.send_audio(call.message.chat.id, file_id)
        else:
            bot.send_document(call.message.chat.id, file_id)

        bot.answer_callback_query(call.id)

    except Exception as e:
        logging.exception(f"Ошибка при отправке файла: {e}")
        bot.answer_callback_query(call.id, "⚠️ Ошибка при отправке файла.")


# ------------------ ОБРАБОТКА КНОПОК ------------------
@bot.message_handler(func=lambda m: is_back_command(m))
def back_handler(message):
    """Обработка кнопки Назад"""
    logging.info(f"Нажата кнопка назад от {message.from_user.id}")
    handle_back_command(message)


@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def help_handler(message):
    """Обработка кнопки Помощь"""
    help_text = (
        "🤖 Bonch inform Bot — помощь\n\n"
        "📚 Лекции — получить материалы\n"
        "ℹ️ О боте — информация о проекте\n"
        "🤖 Чат с нейросетью — общение с AI\n\n"
        "👨‍💼 Для админов:\n"
        "➕ Добавить лекцию\n"
        "📁 Добавить файл\n"
        "📊 Посмотреть базу\n"
        "🗑 Удалить лекцию"
    )
    bot.send_message(message.chat.id, help_text)


@bot.message_handler(func=lambda m: m.text == "ℹ️ О боте")
def about_handler(message):
    """Обработка кнопки О боте"""
    bot.send_message(message.chat.id,
                     "🤖 Bonch inform Bot v2.3\n"
                     "Бот для доступа к лекциям и материалам.\n"
                     "Разработан для удобства студентов.")


@bot.message_handler(func=lambda m: m.text == "🤖 Чат с нейросетью")
def gemini_button_handler(message):
    """Обработка кнопки чата с нейросетью"""
    logging.info(f"Выбор 'Чат с нейросетью' от {message.from_user.id}")
    start_gemini_chat(message)


@bot.message_handler(func=lambda m: user_gemini_states.get(m.from_user.id, False))
def gemini_message_handler(message):
    """Обработка сообщений в чате с Gemini"""
    logging.info(f"Сообщение в чат с Gemini от {message.from_user.id}: {message.text}")
    handle_gemini_message(message)


# ------------------ ОБРАБОТКА НЕИЗВЕСТНЫХ СООБЩЕНИЙ ------------------
@bot.message_handler(content_types=['text', 'photo', 'document', 'audio', 'video', 'voice'])
def universal_handler(message):
    """Универсальный обработчик для всех типов сообщений"""
    try:
        # Если сообщение не текстовое и мы не в режиме загрузки файла
        if message.content_type != 'text':
            state = bot.get_state(message.from_user.id, message.chat.id)
            # Если не в состоянии ожидания файла, игнорируем
            if state != str(UserStates.admin_waiting_file):
                bot.send_message(message.chat.id,
                                 "❌ Я работаю только с текстовыми командами. Используйте кнопки меню.",
                                 reply_markup=create_main_menu(is_admin(message.from_user.id)))
                return

        # Для текстовых сообщений, которые не обработаны другими хэндлерами
        if message.content_type == 'text' and not is_back_command(message):
            logging.info(f"Неизвестная команда: {message.text} от {message.from_user.id}")
            bot.send_message(
                message.chat.id,
                "❌ Неизвестная команда. Используйте кнопки меню.",
                reply_markup=create_main_menu(is_admin(message.from_user.id))
            )

    except Exception as e:
        logging.error(f"Ошибка в универсальном обработчике: {e}")
        bot.send_message(message.chat.id,
                         "⚠️ Произошла ошибка. Возвращаю в главное меню.",
                         reply_markup=create_main_menu(is_admin(message.from_user.id)))


# ------------------ СТАРТ БОТА ------------------
if __name__ == "__main__":
    logging.info("🚀 Бот запущен и ожидает сообщений...")
    bot.infinity_polling()

