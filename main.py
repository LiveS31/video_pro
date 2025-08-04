# main.py 3
import cv2
import time
import os
import datetime
from collections import deque
from rec_foto import screen_mov
import configparser
import telebot

# Глобальный словарь для флагов остановки. Ключ - camera_id, значение - True/False.
stop_video_stream = {}

# Константы для записи видео (время, файлы, кадры)
PRE_MOTION_RECORD_TIME = 10
POST_MOTION_RECORD_TIME = 10
FPS = 20
FOURCC = cv2.VideoWriter_fourcc(*'mp4v')

# Настройка для отправки уведомлений в Telegram
config = configparser.ConfigParser()
with open('info.ini', 'r', encoding='utf-8') as f:
    config.read_file(f)

tel_key = config.get('section1', 'tel_bot')
userid = config.get('section1', 'userid')
bot_instance = telebot.TeleBot(f'{tel_key}')

def video_cap(videos=0, camera_id="default_cam"):
    # Инициализирует и запускает захват видео с камеры
    global stop_video_stream
    stop_video_stream[camera_id] = False

    cap = cv2.VideoCapture(videos)

    if not cap.isOpened():
        error_msg = f"Ошибка: Не удалось открыть видеопоток для '{camera_id.replace('cam', 'камеры: ')}."
        print(error_msg)
        try:
            bot_instance.send_message(int(userid), error_msg)
        except Exception as e:
            print(f"Ошибка при отправке сообщения в Telegram: {e}")
        return

    print(f'Видео запущено для {camera_id.replace('cam', 'камеры: ')} в {time.strftime("%H:%M:%S")}')
    video_start(cap, camera_id)

def video_start(cap, camera_id):

    global stop_video_stream
    times = 0
    recording = False
    motion_detected_time = 0
    out = None
    frame_buffer = deque(maxlen=FPS * PRE_MOTION_RECORD_TIME)

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_size = (frame_width, frame_height)

    if os.name == 'posix':
        video_base_dir = f'/home/lives/Видео/{camera_id}'
        screenshot_base_dir = f'/home/lives/Изображения/{camera_id}'
    else:
        video_base_dir = f'C:\\video\\{camera_id}'
        screenshot_base_dir = f'C:\\Изображения\\{camera_id}'

    os.makedirs(video_base_dir, exist_ok=True)
    os.makedirs(screenshot_base_dir, exist_ok=True)

    while True:
        if stop_video_stream.get(camera_id, False):
            print(f"Получена команда на остановку для {camera_id.replace('cam', 'камера: ')}")
            break

        ret, frame1 = cap.read()
        if not ret:
            print(f"Видеопоток с {camera_id.replace('cam','камеры ')} завершен.")
            break
        
        ret, frame2 = cap.read()
        if not ret:
            break

        frame_buffer.append(frame1.copy())

        diff = cv2.absdiff(frame1, frame2)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 20, 255, cv2.THRESH_BINARY)
        dilated = cv2.dilate(thresh, None, iterations=3)
        contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        motion_found = False
        for contour in contours:
            if cv2.contourArea(contour) < 900:
                continue

            motion_found = True
            motion_detected_time = time.time()
            
            (x, y, w, h) = cv2.boundingRect(contour)
            cv2.rectangle(frame1, (x, y), (x + w, y + h), (0, 255, 0), 2)

            if int(time.time()) > times:
                info = (f"Обнаружено движение!\n{camera_id.replace('cam', 'камера: ')}"
                        f"\n{time.strftime('%H:%M:%S %d.%m.%Y')}")
                print(screen_mov(frame1, time.strftime('%H%M%S_%d%m%Y'), camera_id))  # если виксация движения ненужно frame2
                times = int(time.time()) + 120  # поставить нужное время для отправки скринов сейча ~ 2 мин
                try:
                    bot_instance.send_message(int(userid), info)
                except Exception as e:
                    print(f"Ошибка при отправке сообщения в Telegram: {e}")

            break

        if motion_found and not recording:
            recording = True
            video_cam_day_dir = os.path.join(video_base_dir, f"video_{datetime.datetime.now().strftime('%d%m%Y')}")
            os.makedirs(video_cam_day_dir, exist_ok=True)
            
            video_filename = os.path.join(
                video_cam_day_dir,
                f"motion_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{camera_id}.mp4"
            )
            out = cv2.VideoWriter(video_filename, FOURCC, FPS, frame_size)

            for buffered_frame in frame_buffer:
                out.write(buffered_frame)

            info = (f"Запись видео с {camera_id.replace('cam','камеры ')}")
            try:
                bot_instance.send_message(int(userid), info)
            except Exception as e:
                print(f"Ошибка при отправке сообщения в Telegram: {e}")



        if recording:
            out.write(frame1) # если движение отображать ненужно! заменить на 2

        if not motion_found and recording and (time.time() - motion_detected_time) > POST_MOTION_RECORD_TIME:
            recording = False
            out.release()
            out = None

            info = (f"Запись видео с {camera_id.replace('cam', 'камеры ')}\n"
                    f"завершено в {time.strftime('%H:%M:%S %d.%m.%Y')}.\n"
                    f"Файл:\nmotion_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{camera_id}.mp4\n")

            try:
                bot_instance.send_message(int(userid), info)
            except Exception as e:
                print(f"Ошибка при отправке сообщения в Telegram: {e}")
            print()
        
        cv2.imshow(f"Motion Detection - {camera_id.replace('cam','camera ')}", frame1)

        if cv2.waitKey(25) & 0xFF == ord('q'):
            print(f"Окно для {camera_id.replace('cam','камеры ')} закрыто вручную.")
            stop_video_stream[camera_id] = True
            break

    cap.release()
    if out is not None:
        out.release()
    cv2.destroyAllWindows()
    print(f"Видео {camera_id.replace('cam','камеры ')} остановлено.")

