import logging
from telebot import types
from common_functions import bot, is_admin, go_home, create_back_button, UserStates, is_back_command, safe_delete_state
import database


# ------------------ ОБРАБОТКА ДОБАВЛЕНИЯ ЛЕКЦИИ ------------------
@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and m.text == "➕ Добавить лекцию")
def admin_add_lecture(message):
    """Шаг 1: Админ выбирает курс"""
    try:
        msg = bot.send_message(
            message.chat.id,
            "Введите номер курса (1–4):",
            reply_markup=create_back_button()
        )
        bot.set_state(message.from_user.id, UserStates.admin_entering_course, message.chat.id)
        bot.register_next_step_handler(msg, process_admin_course)
    except Exception as e:
        logging.error(f"Ошибка в admin_add_lecture: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка при запуске добавления лекции.")


def process_admin_course(message):
    """Обработка введённого курса"""
    try:
        if is_back_command(message):
            go_home(message.chat.id, message.from_user.id)
            return

        course = int(message.text)
        if not (1 <= course <= 4):
            msg = bot.send_message(message.chat.id, "❌ Курс должен быть от 1 до 4. Введите номер курса:")
            bot.register_next_step_handler(msg, process_admin_course)
            return

        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data["course"] = course

        bot.set_state(message.from_user.id, UserStates.admin_entering_topic, message.chat.id)
        msg = bot.send_message(
            message.chat.id,
            f"Введите название темы для курса {course}:",
            reply_markup=create_back_button()
        )
        bot.register_next_step_handler(msg, process_admin_topic)

    except ValueError:
        msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 4:")
        bot.register_next_step_handler(msg, process_admin_course)
    except Exception as e:
        logging.error(f"Ошибка в process_admin_course: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка при обработке курса.")
        go_home(message.chat.id, message.from_user.id)


def process_admin_topic(message):
    """Обработка введённой темы и добавление лекции"""
    try:
        if is_back_command(message):
            go_home(message.chat.id, message.from_user.id)
            return

        topic = message.text.strip()
        if not topic:
            msg = bot.send_message(message.chat.id, "❌ Название темы не может быть пустым. Введите название темы:")
            bot.register_next_step_handler(msg, process_admin_topic)
            return

        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            course = data.get("course")

        if database.lecture_exists(course, topic):
            bot.send_message(message.chat.id, "❌ Такая лекция уже существует.")
        else:
            database.add_lecture(course, topic)
            bot.send_message(message.chat.id, f"✅ Лекция '{topic}' для курса {course} успешно добавлена!")
            logging.info(f"Создана лекция: курс={course}, тема='{topic}'")

    except Exception as e:
        logging.error(f"Ошибка при добавлении лекции: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка при добавлении. Попробуйте позже.")

    safe_delete_state(message.from_user.id, message.chat.id)
    go_home(message.chat.id, message.from_user.id)


# ------------------ ДОБАВЛЕНИЕ ФАЙЛА К ЛЕКЦИИ ------------------
@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and m.text == "📁 Добавить файл")
def admin_add_file_start(message):
    """Шаг 1: админ вводит номер курса"""
    try:
        msg = bot.send_message(message.chat.id, "Введите номер курса (1–4):", reply_markup=create_back_button())
        bot.set_state(message.from_user.id, UserStates.admin_entering_course, message.chat.id)
        bot.register_next_step_handler(msg, admin_add_file_choose_topic)
    except Exception as e:
        logging.error(f"Ошибка в admin_add_file_start: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка при запуске добавления файла.")


def admin_add_file_choose_topic(message):
    """Шаг 2: выбор темы"""
    try:
        if is_back_command(message):
            go_home(message.chat.id, message.from_user.id)
            return

        course = int(message.text)
        if not (1 <= course <= 4):
            msg = bot.send_message(message.chat.id, "❌ Курс должен быть от 1 до 4. Введите номер курса:")
            bot.register_next_step_handler(msg, admin_add_file_choose_topic)
            return

        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data["course"] = course

        topics = database.get_topics_by_course(course)
        if not topics:
            bot.send_message(message.chat.id, "📭 Для этого курса нет лекций. Сначала добавьте лекцию.")
            go_home(message.chat.id, message.from_user.id)
            return

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for topic in topics:
            markup.add(types.KeyboardButton(f"🔖 {topic}"))
        markup.add(types.KeyboardButton("🔙 Назад"))

        msg = bot.send_message(message.chat.id, "Выберите тему:", reply_markup=markup)
        bot.set_state(message.from_user.id, UserStates.admin_choosing_file_type, message.chat.id)
        bot.register_next_step_handler(msg, admin_add_file_choose_type)

    except ValueError:
        msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 4:")
        bot.register_next_step_handler(msg, admin_add_file_choose_topic)
    except Exception as e:
        logging.error(f"Ошибка в admin_add_file_choose_topic: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка при выборе темы.")
        go_home(message.chat.id, message.from_user.id)


def admin_add_file_choose_type(message):
    """Шаг 3: выбор типа файла"""
    try:
        if is_back_command(message):
            go_home(message.chat.id, message.from_user.id)
            return

        if not message.text.startswith("🔖 "):
            msg = bot.send_message(message.chat.id, "❌ Нажмите на тему из списка или '🔙 Назад'.")
            bot.register_next_step_handler(msg, admin_add_file_choose_type)
            return

        topic = message.text.replace("🔖 ", "", 1).strip()
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data["topic"] = topic

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton("🎧 Аудио (mp3)"),
            types.KeyboardButton("📄 Документ"),
            types.KeyboardButton("📊 Презентация"),
            types.KeyboardButton("🖼 Фото")
        )
        markup.add(types.KeyboardButton("🔙 Назад"))

        msg = bot.send_message(message.chat.id, "Выберите тип файла для загрузки:", reply_markup=markup)
        bot.set_state(message.from_user.id, UserStates.admin_waiting_file, message.chat.id)
        bot.register_next_step_handler(msg, admin_add_file_wait_for_file)

    except Exception as e:
        logging.error(f"Ошибка в admin_add_file_choose_type: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка при выборе типа файла.")
        go_home(message.chat.id, message.from_user.id)


def admin_add_file_wait_for_file(message):
    """Шаг 4: ожидание выбора типа файла"""
    try:
        if is_back_command(message):
            go_home(message.chat.id, message.from_user.id)
            return

        file_types = ["🎧 Аудио (mp3)", "📄 Документ", "📊 Презентация", "🖼 Фото"]
        if message.text not in file_types:
            msg = bot.send_message(message.chat.id, "❌ Сначала выберите тип файла из меню.")
            bot.register_next_step_handler(msg, admin_add_file_wait_for_file)
            return

        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data["file_type_choice"] = message.text

        bot.send_message(message.chat.id, "Теперь отправьте сам файл. Если это аудио — отправьте как голос/аудио.")
        bot.register_next_step_handler(message, admin_process_uploaded_file)

    except Exception as e:
        logging.error(f"Ошибка в admin_add_file_wait_for_file: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка при обработке типа файла.")
        go_home(message.chat.id, message.from_user.id)


def admin_process_uploaded_file(message):
    """Обработка загруженного файла"""
    try:
        if is_back_command(message):
            safe_delete_state(message.from_user.id, message.chat.id)
            go_home(message.chat.id, message.from_user.id)
            return

        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            course = data.get("course")
            topic = data.get("topic")
            choice = data.get("file_type_choice")

        if not all([course, topic, choice]):
            bot.send_message(message.chat.id, "⚠️ Неверный порядок действий. Начните заново.")
            go_home(message.chat.id, message.from_user.id)
            return

        # Определяем тип контента и получаем file_id
        file_type_map = {
            "🎧 Аудио (mp3)": ("audio", getattr(message, 'audio', None) or getattr(message, 'voice', None)),
            "📄 Документ": ("document", getattr(message, 'document', None)),
            "📊 Презентация": ("presentation", getattr(message, 'document', None)),
            "🖼 Фото": ("photo", getattr(message, 'photo', None))
        }

        file_type, file_obj = file_type_map.get(choice, (None, None))

        if not file_obj:
            bot.send_message(message.chat.id, f"❌ Ожидался {choice.split()[0]}. Отправьте файл или нажмите '🔙 Назад'.")
            bot.register_next_step_handler(message, admin_process_uploaded_file)
            return

        # Для фото берем последний (наибольший) размер
        if file_type == "photo" and file_obj:
            file_id = file_obj[-1].file_id
        else:
            file_id = file_obj.file_id

        database.update_lecture_file(course, topic, file_type, file_id)
        bot.send_message(message.chat.id, f"✅ Файл ({choice}) успешно прикреплён к лекции '{topic}' (курс {course}).")
        logging.info(f"Админ добавил файл: курс={course}, тема='{topic}', тип={file_type}")

    except Exception as e:
        logging.error(f"Ошибка при сохранении файла в БД: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка при сохранении файла. Попробуйте позже.")

    safe_delete_state(message.from_user.id, message.chat.id)
    go_home(message.chat.id, message.from_user.id)


# ------------------ ПРОСМОТР БАЗЫ ДАННЫХ ------------------
@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and m.text == "📊 База данных")
def admin_view_db(message):
    """Просмотр всех лекций в базе"""
    try:
        rows = database.get_all_lectures()
        if not rows:
            bot.send_message(message.chat.id, "📭 В базе нет лекций.")
            return

        text_lines = ["📚 Список лекций:"]
        for course, topic, audio_id, doc_id, pres_id, photo_id in rows:
            parts = [f"Курс {course} — {topic}"]
            files = []
            if audio_id: files.append("Аудио")
            if doc_id: files.append("Документ")
            if pres_id: files.append("Презентация")
            if photo_id: files.append("Фото")
            if files: parts.append(f"({', '.join(files)})")
            text_lines.append(" — ".join(parts))

        # Разбиваем длинные сообщения
        full_text = "\n".join(text_lines)
        if len(full_text) > 4000:
            for i in range(0, len(full_text), 4000):
                bot.send_message(message.chat.id, full_text[i:i + 4000])
        else:
            bot.send_message(message.chat.id, full_text)

    except Exception as e:
        logging.error(f"Ошибка при просмотре БД: {e}")
        bot.send_message(message.chat.id, "⚠️ Ошибка при получении данных БД.")


# ------------------ УДАЛЕНИЕ ЛЕКЦИИ ------------------
@bot.callback_query_handler(
    func=lambda call: call.data.startswith(("delete_lecture_", "delete_confirm_", "delete_cancel_")))
def handle_delete_lecture(call):
    """Обработка удаления лекции с подтверждением"""
    try:
        if call.data.startswith("delete_confirm_"):
            # Подтверждение удаления
            payload = call.data[len("delete_confirm_"):]
            course_str, topic_enc = payload.split("_", 1)
            course = int(course_str)
            topic = topic_enc.replace("~", " ")

            database.delete_lecture(course, topic)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🗑 Лекция «{topic}» для курса {course} успешно удалена!"
            )

        elif call.data.startswith("delete_cancel_"):
            # Отмена удаления
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ Удаление лекции отменено."
            )

        else:
            # Запрос подтверждения
            payload = call.data[len("delete_lecture_"):]
            course_str, topic_enc = payload.split("_", 1)
            course = int(course_str)
            topic = topic_enc.replace("~", " ")

            if not database.lecture_exists(course, topic):
                bot.answer_callback_query(call.id, "❌ Лекция не найдена.")
                return

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Да", callback_data=f"delete_confirm_{course}_{topic_enc}"),
                types.InlineKeyboardButton("❌ Нет", callback_data=f"delete_cancel_{course}_{topic_enc}")
            )
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"⚠️ Вы уверены, что хотите удалить лекцию «{topic}» (курс {course})?",
                reply_markup=markup
            )

    except Exception as e:
        logging.exception("Ошибка при удалении лекции:")
        bot.answer_callback_query(call.id, "⚠️ Ошибка при удалении.")


# ------------------ ПРОСМОТР ФОТО ------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("view_photo_"))
def handle_view_photo(call):
    """Отправка прикреплённого фото пользователю"""
    try:
        payload = call.data[len("view_photo_"):]
        course_str, topic_enc = payload.split("_", 1)
        course = int(course_str)
        topic = topic_enc.replace("~", " ")

        photo_id = database.get_photo_id(course, topic)
        if not photo_id:
            bot.answer_callback_query(call.id, "❌ Фото не найдено.")
            return

        bot.send_photo(
            call.message.chat.id,
            photo_id,
            caption=f"📸 Фото по теме «{topic}» (курс {course})"
        )
        bot.answer_callback_query(call.id)

    except Exception as e:
        logging.exception("Ошибка при отправке фото:")
        bot.answer_callback_query(call.id, "⚠️ Ошибка при показе фото.")

