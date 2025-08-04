# rec_foto.py
import os
import cv2
import configparser
import telebot

config = configparser.ConfigParser()
with open('info.ini', 'r') as f:
    config.read_file(f)

tel_key = config.get('section1', 'tel_bot') # получаем значение бота
userid = config.get('section1', 'userid')  # получаем значение пользователя
bot_instance = telebot.TeleBot(f'{tel_key}') # вводим токен бота в переменную

def screen_mov(frame, times, camera_id="default_cam"):
    """Сохраняет кадр (скриншот) при обнаружении движения."""
    
    # --- Формирование пути для сохранения ---
    # Путь зависит от ОС
    if os.name == 'posix': # Linux/macOS
        # ИМЯ ПАПКИ
        screenshot_dir = f"/home/lives/Изображения/{camera_id}/mot_pic{times[6:]}"
    else: # Windows
        screenshot_dir = f"C:\\Изображения\\{camera_id}\\mot_pic{times[6:]}"

    # Создаем папку, если ее нет
    os.makedirs(screenshot_dir, exist_ok=True)

    filename = os.path.join(screenshot_dir, f"foto_detect_{times}_{camera_id}.jpg")
    cv2.imwrite(filename, frame)
    with open(f'{filename}', 'rb') as f:
        bot_instance.send_photo(int(userid), f)

    return f"Скриншот для {camera_id.replace('cam', 'камеры ')} сохранен: {os.path.basename(filename)}"


