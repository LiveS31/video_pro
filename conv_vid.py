# конвектор
import time
from moviepy import VideoFileClip
import os
import telebot
import configparser

config = configparser.ConfigParser()
with open('info.ini', 'r', encoding='utf-8') as f:
    config.read_file(f)

tel_key = config.get('section1', 'tel_bot')
userid = config.get('section1', 'userid')
bot_instance = telebot.TeleBot(f'{tel_key}') # вводим токен бота в переменную


if os.name == 'posix':
    video_base_dir = os.path.expanduser("~/Видео")
    sl = '/'
else:
    video_base_dir = 'C:\\video'
    sl = '\\'

# запускаем конвертации по n дней.
def start_conv_video(days=7):
    now = time.time()
    for root, dirs, files in os.walk(video_base_dir):
        if 'archive' not in root:
            archive_dir = os.path.join(root, 'archive')
            if 'archive' not in root and files:
                try:
                    os.mkdir(archive_dir)
                    bot_instance.send_message(int(userid), "Папка 'archive' создана")
                except Exception :
                    bot_instance.send_message(int(userid), "Папка 'archive' существует")

            for file in files:
                vide_file = os.path.join(root, file)
                if (now - os.path.getctime(vide_file)) / (24 * 3600) >= days:
                    if vide_file.lower().endswith('.mp4'):
                        bot_instance.send_message(int(userid), f'Перекодирование файла\n{file}')
                        try:
                            clip = VideoFileClip(vide_file)
                            new_filepath = os.path.join(archive_dir, file.replace('.mp4', '_conv.mp4'))
                            # Параметр threads=1 для использования одного ядра (можно менять или вообзе загнать в переменную
                            clip.write_videofile(new_filepath, audio=False, codec="libx264", threads=1)
                            clip.close()
                            bot_instance.send_message(int(userid), f'Архивация {file} завершена.')
                            os.remove(vide_file)
                        except Exception:
                            bot_instance.send_message(int(userid), f'Ошибка кодировки файла\n{file}')
    return

