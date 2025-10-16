# teleg_bot.py
import configparser
import os
import telebot
from telebot import types
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import threading
####
from rec_foto import status_cam
from conv_vid import del_and_free
######темп
import shutil
##### nemp


# Импортируем ВЕСЬ  main
import main
CAMERA_INFO = {}
config = configparser.ConfigParser()
with open('info.ini', 'r', encoding='utf-8') as f:
    config.read_file(f)

vid_cam = config.get('section2', 'id_cam').split(', ')

#  НАСТРОЙКИ КАМЕР
# Определение камер:
# "Название для кнопки": {"index": системный индекс камеры, "id": уникальный строковый идентификатор}

for i in range(len(vid_cam)):
    if vid_cam[i].isdigit():
        vid_cam[i] = int(vid_cam[i])
    CAMERA_INFO[f"Камера {i+1}"] = {"index": vid_cam[i],
                     "id": f"cam{i + 1}"}
#  КОНЕЦ НАСТРОЕК КАМЕР

# Глобальные переменные для управления видеопотоками
camera_threads = {} # {"cam_id": Thread_object} - хранит потоки для каждой камеры
is_video_running = {info["id"]: False for info in CAMERA_INFO.values()} # {"cam_id": True/False} - хранит состояние потока

#  Чтение конфигурации из info.ini
config = configparser.ConfigParser()
with open('info.ini', 'r', encoding='utf-8') as f:
    config.read_file(f)
# заполняем параметры из файла
tel_key = config.get('section1', 'tel_bot')
userid = config.get('section1', 'userid')
VideoBot = telebot.TeleBot(f'{tel_key}')
# пути для сохранения видео
video_base = config.get('section2', 'video')
# пути для сохранения скринов
screen_dir = config.get('section2', 'pict')


#  Определение путей к файлам в зависимости от ОС
if os.name == 'posix': # для Linux/macOS
    base_video_path = video_base
    base_screenshot_path = screen_dir
    # base_video_path = f'/home/lives/Видео' # изменить на свой путь
    # base_screenshot_path = f"/home/lives/Изображения"
else: # для Windows
    base_video_path = video_base
    base_screenshot_path = screen_dir
    # base_video_path = f'C:\\video'
    # base_screenshot_path = f"C:\\Изображения"

def get_folders_list(base_dir, camera_id):
    """Возвращает список папок для указанной камеры."""
    full_path = os.path.join(base_dir, camera_id)
    if not os.path.exists(full_path):
        os.makedirs(full_path, exist_ok=True)
        return [] # Возвращаем пустой список, если только что создали
    try:
        # Возвращаем только директории
        return [d for d in os.listdir(full_path) if os.path.isdir(os.path.join(full_path, d))]
    except Exception as e:
        print(f"Ошибка при получении списка папок из {full_path}: {e}")
        return []

# --- Клавиатура основного меню ---
markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
markup.add(
    KeyboardButton("ВИДЕО 📹"),
    KeyboardButton("ФОТО 📷"),
    KeyboardButton('Запустить видео'),
    KeyboardButton('Остановить поток'),
    KeyboardButton(f'Место доступное на диске: {del_and_free(0)[1]}%')
    )

@VideoBot.message_handler(commands=['start'])
def start_message(message):
    """Обработчик команды /start."""
    VideoBot.send_message(message.chat.id, "Привет! Выбери действие:", reply_markup=markup)

@VideoBot.message_handler(content_types=['text'])
def message_user(message):
    """Обработчик текстовых сообщений и кнопок главного меню."""
    if not (message.from_user.id == int(userid)):
        VideoBot.send_message(message.chat.id, "У вас нет доступа.")
        return


    action_map = {
        'запустить видео': 'start_cam',
        'остановить поток': 'stop_cam',
        'видео 📹': 'select_cam_video',
        'фото 📷': 'select_cam_foto',

    }

    # Получаем префикс для callback_data на основе текста сообщения
    action_prefix = action_map.get(message.text.lower())
####################################################################################
    # 6.   % заполненности диска
    if message.text[:5] == 'Место':
        info = del_and_free()
        markup1 = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        markup1.add(
            KeyboardButton("ВИДЕО 📹"),
            KeyboardButton("ФОТО 📷"),
            KeyboardButton('Запустить видео'),
            KeyboardButton('Остановить поток'),
            KeyboardButton(f'Место доступное на диске: {del_and_free(0)[1]}%')
        )
        VideoBot.send_message(message.chat.id, f'{info[0][:-7]}\n'
                                               f'Доступно: {info[1]}%', reply_markup=markup1)
        return
####################################################################################

    if not action_prefix:
        VideoBot.send_message(message.chat.id, "Неизвестная команда.", reply_markup=markup)
        return

    # Создаем клавиатуру для выбора камеры
    cam_selection_markup = types.InlineKeyboardMarkup(row_width=1)
    for cam_name, cam_data,  in CAMERA_INFO.items():
        # ИСПОЛЬЗУЕМ ДВОЕТОЧИЕ (:) КАК РАЗДЕЛИТЕЛЬ
        callback_data = f'{action_prefix}:{cam_data["id"]}'
        # вот как оставить просто камера или ее номер, или как она названа
        rt = (f'\nИмя: {cam_data["index"]}')
        #cam_selection_markup.add(types.InlineKeyboardButton(cam_name, callback_data=callback_data))
        cam_selection_markup.add(types.InlineKeyboardButton((cam_name+rt), callback_data=callback_data))

    action_messages = {
        'start_cam': "Какую камеру запустить?",
        'stop_cam': "Какую камеру остановить?",
        'select_cam_video': "Выбери камеру для просмотра видео:",
        'select_cam_foto': "Выбери камеру для просмотра фото:",

    }
    VideoBot.send_message(message.chat.id, action_messages[action_prefix], reply_markup=cam_selection_markup)


@VideoBot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    # Основной обработчик inline-кнопок
    if not (call.from_user.id == int(userid)):
        VideoBot.answer_callback_query(call.id, "У вас нет доступа.")
        return


    #  CALL.DATA
    # двоеточие как разделитель, чтобы избежать конфликтов с именами файлов
    # Форматы:
    # 'действие:id_камеры' -> ['start_cam', 'cam1']
    # 'действие:id_камеры:имя_папки' -> ['skan_video', 'cam1', 'video_01012024']
    # 'действие:id_камеры:имя_папки:имя_файла' -> ['up', 'cam1', 'video_01012024', 'motion.mp4']
    parts = call.data.split(':', maxsplit=3)
    action = parts[0]
    cam_id = parts[1] if len(parts) > 1 else None
    folder_name = parts[2] if len(parts) > 2 else None
    file_name = parts[3] if len(parts) > 3 else None



    # 1. ЗАПУСК ПОТОКА
    if action == 'start_cam':
        cam_index = next((info["index"] for name, info in CAMERA_INFO.items() if info["id"] == cam_id), None)

        if cam_index is None:
            VideoBot.send_message(call.message.chat.id, f"Ошибка: Камера с ID {cam_id.replace('cam', '')} не найдена.")
            return

        if is_video_running.get(cam_id) and camera_threads.get(cam_id) and camera_threads[cam_id].is_alive():
            VideoBot.send_message(call.message.chat.id, f"Поток '{cam_id.replace('cam', 'камеры ')}' уже запущен.")
        else:
            VideoBot.send_message(call.message.chat.id, f"Запуск потока '{cam_id.replace('cam', 'камеры ')}'...")
            thread = threading.Thread(target=main.video_cap, args=(cam_index, cam_id,))
            thread.start()
            camera_threads[cam_id] = thread
            is_video_running[cam_id] = True

    #  2. ОСТАНОВКА ПОТОКА
    elif action == 'stop_cam':
        if is_video_running.get(cam_id) and camera_threads.get(cam_id) and camera_threads[cam_id].is_alive():
            main.stop_video_stream[cam_id] = True # Устанавливаем флаг остановки
            is_video_running[cam_id] = False
            VideoBot.send_message(call.message.chat.id, f"Отправлена команда остановки "
                                                        f"{cam_id.replace('cam', 'камеры: ')} .\n"
                                                        f"Может занять время...")
        else:
            VideoBot.send_message(call.message.chat.id, f"Поток для '{cam_id.replace('cam', 'камеры ')}' не запущен.")

    #  3. ВЫБОР КАМЕРЫ ДЛЯ ПРОСМОТРА ФАЙЛОВ
    elif action in ['select_cam_video', 'select_cam_foto']:
        base_path = base_video_path if action == 'select_cam_video' else base_screenshot_path
        scan_action = 'skan_video' if action == 'select_cam_video' else 'skan_foto'
        
        folders = get_folders_list(base_path, cam_id)
        if not folders:
            VideoBot.send_message(call.message.chat.id, f'Папка с файлами для '
                                                        f'{cam_id.replace('cam', 'камеры ')} пуста или не существует.')
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for folder in folders:
            callback_data = f'{scan_action}:{cam_id}:{folder}'
            markup.add(types.InlineKeyboardButton(folder, callback_data=callback_data))
        VideoBot.send_message(call.message.chat.id,
                              f'Выбери папку для {cam_id.replace('cam', 'камеры ')}:', reply_markup=markup)

    #  4. СКАНИРОВАНИЕ ПАПКИ (ПОКАЗ ФАЙЛОВ)
    elif action in ['skan_video', 'skan_foto']:
        base_path = base_video_path if action == 'skan_video' else base_screenshot_path
        current_path = os.path.join(base_path, cam_id, folder_name)

        if not os.path.exists(current_path):
            VideoBot.send_message(call.message.chat.id, "Ошибка: Папка не найдена.")
            return

        files = [f for f in os.listdir(current_path) if os.path.isfile(os.path.join(current_path, f))]
        if not files:
            VideoBot.send_message(call.message.chat.id, 'В этой папке нет файлов.')
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for f_name in files:
            # Передаем все части дальше, используя ':'
            callback_data = f'up:{cam_id}:{folder_name}:{f_name}'
            markup.add(types.InlineKeyboardButton(f_name, callback_data=callback_data))
        VideoBot.send_message(call.message.chat.id, 'Выбери файл для просмотра:', reply_markup=markup)

    #  5. ОТПРАВКА ФАЙЛА ПОЛЬЗОВАТЕЛЮ
    elif action == 'up':
        is_video_file = file_name.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))
        base_path = base_video_path if is_video_file else base_screenshot_path
        
        # Собираем корректный путь из разобранных частей
        file_path = os.path.join(base_path, cam_id, folder_name, file_name)

        if not os.path.exists(file_path):
            VideoBot.send_message(call.message.chat.id, f"Файл не найден! Ожидался путь: {file_path}")
            return
        
        try:
            with open(file_path, 'rb') as f:
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                    VideoBot.send_photo(call.message.chat.id, f)
                elif is_video_file:
                    VideoBot.send_video(call.message.chat.id, f)
                else:
                    VideoBot.send_document(call.message.chat.id, f)
        except telebot.apihelper.ApiTelegramException as e:
            if "file is too big" in str(e):
                VideoBot.send_message(call.message.chat.id, "Файл слишком большой для отправки.")
            else:
                VideoBot.send_message(call.message.chat.id, f"Ошибка Telegram API: {e}")
        except Exception as e:
            VideoBot.send_message(call.message.chat.id, f"Не удалось отправить файл: {e}")

    else:
        VideoBot.answer_callback_query(call.id, "Неизвестное действие.")



status_cam( "Бот запущен.\nВыберите действия или\nнажмите /start для вызова меню")
VideoBot.polling(none_stop=True, interval=0)


