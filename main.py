# main.py
import cv2
import time
import os
import datetime
from collections import deque
from rec_foto import screen_mov, status_cam
from conv_vid import start_conv_video, del_and_free
from multiprocessing import Process
import configparser
import telebot


#  Глобальный словарь для флагов остановки. .
stop_video_stream = {}
cam_inf = {}

# Константы для записи видео (время, файлы, кадры)
FOURCC = cv2.VideoWriter_fourcc(*'mp4v')

##############################################################################################
# Настройка для отправки уведомлений в Telegram
config = configparser.ConfigParser()
with open('info.ini', 'r', encoding='utf-8') as f:
    config.read_file(f)

tel_key = config.get('section1', 'tel_bot')
userid = config.get('section1', 'userid')
vid_cam = config.get('section2', 'id_cam').split(', ')
# архивация через x дней посл записи
arh_day = int(config.get('section2', 'day_arh'))
# время запуска архивации
time_arh = config.get('section2', 'arh_time').replace(':', '')
# пред.запись
pre_motion_record_tme = int(config.get('section2', 'pre_record_time'))
# пост.запсь
post_motion_record_time = int(config.get('section2', 'post_record_time'))
# кадры
fps = int(config.get('section2', 'fps_inf'))
# Новые параметры для разрешения
frame_width_conf = int(config.get('section2', 'width'))
frame_height_conf = int(config.get('section2', 'height'))
# пути для сохранения видео
video_base = config.get('section2', 'video')
# пути для сохранения скринов
screen_dir = config.get('section2', 'pict')
# время старта очитки диска при условии
time_disk = config.get('section2', 'time_disk')

############################################################################################
bot_instance = telebot.TeleBot(f'{tel_key}')
############################################################################################


def video_cap(videos=0, camera_id="default_cam"):
    # Инициализирует и запускает захват видео с камеры
    global stop_video_stream
    stop_video_stream[camera_id] = False

    cap = cv2.VideoCapture(videos)

    if not cap.isOpened():
        error_msg = f"Ошибка: Не удалось открыть видеопоток для '{camera_id.replace('cam', 'камеры: ')}."
        status_cam(error_msg)
        try:
            bot_instance.send_message(int(userid), error_msg)
        except Exception as e:
            print(f"Ошибка при отправке сообщения в Telegram: {e}")
        return

    status_cam(f'Видео запущено для {camera_id.replace('cam', 'камеры: ')} в {time.strftime("%H:%M:%S")}')
    video_start(cap, camera_id)
    cam_inf[f'{camera_id}'] = 0


def video_start(cap, camera_id):  # Аргумент здесь называется camera_id
    global stop_video_stream, rec_time
    recording = False
    motion_detected_time = 0
    out = None
    prev_frame = None
    frame_buffer = deque(maxlen=fps * pre_motion_record_tme)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width_conf)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height_conf)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    frame_size = (frame_width, frame_height)

    if os.name == 'posix':
        video_base_dir = f'{video_base}/{camera_id}'
        screenshot_base_dir = f'{screen_dir}/{camera_id}'
    else:
        video_base_dir = f'{video_base}\\{camera_id}'
        screenshot_base_dir = f'{screen_dir}\\{camera_id}'

    os.makedirs(video_base_dir, exist_ok=True)
    os.makedirs(screenshot_base_dir, exist_ok=True)

    while True:
        if stop_video_stream.get(camera_id, False):
            status_cam(f"Получена команда на остановку для {camera_id.replace('cam', 'камера: ')}")
            break

        ret, frame1 = cap.read()
        if not ret:
            status_cam(f"Видеопоток с {camera_id.replace('cam', 'камеры: ')} завершен.")
            break
        gray_frame1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)

        motion_found = False

        if prev_frame is not None:
            diff = cv2.absdiff(prev_frame, gray_frame1)
            blur = cv2.GaussianBlur(diff, (5, 5), 0)
            _, thresh = cv2.threshold(blur, 20, 255, cv2.THRESH_BINARY)
            dilated = cv2.dilate(thresh, None, iterations=3)
            contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                if cv2.contourArea(contour) < 1000:
                    continue

                motion_found = True  # обнаружение движения
                motion_detected_time = time.time()

                (x, y, w, h) = cv2.boundingRect(contour)
                cv2.rectangle(frame1, (x, y), (x + w, y + h), (0, 255, 0), 1)

                ###################################################################################################
                # делаем только одно срабатывание для одной камеры
                if recording:
                    #  Замена cam_id на camera_id, чтобы не было конфликта
                    if cam_inf[f'{camera_id}'] == 0:
                        cam_inf[f'{camera_id}'] = 1

                        #  Замена cam_id на camera_id, чтобы не было конфликта
                        screen_mov(frame1, time.strftime('%H%M%S_%d%m%Y'),
                                   camera_id)
                        #  Замена cam_id на camera_id, чтобы не было конфликта
                        status_cam(f"Обнаружено движение!\n{camera_id.replace('cam', 'Камера: ')}"
                                   f"\n{time.strftime('%H:%M:%S\n%d.%m.%Y')}\n"
                                   f"Запись видео активна.")
                # модуль закончен
                ############################################################################################################

                break

            ###########################################################################################################
            #  Запуск конвертации в отдельном процессе в заданное время
            if time.strftime('%H%M') == time_arh:  # условия для запуска конвертации
                try:
                    p = Process(target=start_conv_video,
                                args=(arh_day,))  # <--- указываем количество дней для архивации
                    p.start()  # запускаем фунцию
                    bot_instance.send_message(int(userid), f'Запущен процесс конвертации видео...\n'
                                                           f"{datetime.datetime.now().strftime('%H:%M:%S %d.%m.%y')}")

                    time.sleep(61)  # Чтобы не запускать процесс каждую секунду в указанную минуту
                except Exception as e:
                    bot_instance.send_message(int(userid), f'Ошибка при запуске процесса конвертации: {e}\n'
                                                           f"{datetime.datetime.now().strftime('%H:%M:%S %d.%m.%y')}")

        ############################################################################################################
        # Запуск очистки и проверки заполнения диска
        if time.strftime('%H%M') == time_disk:
            try:
                del_and_free()
            except Exception as e:
                print(f'Ошибка запуска {e}')
        ###########################################################################################################

        prev_frame = gray_frame1.copy()

        # Только сброс счетчика
        if not recording:
            #  Замена cam_id на camera_id, чтобы не было конфликта
            cam_inf[f'{camera_id}'] = 0
        # --------------------------------------------------------

        ####################################################
        # добавляем время на видеозапись
        current_time_str = datetime.datetime.now().strftime('%H:%M:%S %d.%m.%y')

        # ну и все это засовываем в кадр
        cv2.putText(frame1, current_time_str, (frame_width - 230, frame_height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

        frame_buffer.append(frame1.copy())
        # время добавлено
        ####################################################

        if motion_found and not recording:
            recording = True
            video_cam_day_dir = os.path.join(video_base_dir, f"video_{datetime.datetime.now().strftime('%d%m%Y')}")
            os.makedirs(video_cam_day_dir, exist_ok=True)

            video_filename = os.path.join(
                video_cam_day_dir,
                #  Замена cam_id на camera_id, чтобы не было конфликта
                f"motion_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{camera_id}.mp4"
            )
            ##########################
            # Загоняем в одну переменную
            rec_time = os.path.join(
                video_cam_day_dir,
                #  Замена cam_id на camera_id, чтобы не было конфликта
                f"motion_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{camera_id}.mp4")
            out = cv2.VideoWriter(video_filename, FOURCC, fps, frame_size)

            for buffered_frame in frame_buffer:
                out.write(buffered_frame)

        if recording:
            out.write(frame1)

        if not motion_found and recording and (time.time() - motion_detected_time) > post_motion_record_time:
            recording = False
            out.release()
            out = None

           ######## добаляем кнопку
            #делаем отправлку через #  5. ОТПРАВКА ФАЙЛА ПОЛЬЗОВАТЕЛЮ в teleg_bot
            parts = rec_time.split(os.sep) # расскладываем на путь (для отправки в ->
            file_name = parts[-1]
            folder_name = parts[-2]
            callback_data = f'up:{camera_id}:{folder_name}:{file_name}'
            print( callback_data)
            print(rec_time)

            # Создаём клавиатуру
            markup = telebot.types.InlineKeyboardMarkup(row_width=1)
            markup.add(telebot.types.InlineKeyboardButton(f"Скачать файл",
                                                          callback_data=callback_data))

            info = f"Запись видео с {camera_id.replace('cam', 'камеры: ')} завершена.\n"

            try:
                bot_instance.send_message(int(userid), info, reply_markup=markup)
            except Exception as e:
                print(f"Ошибка при отправке сообщения в Telegram: {e}")


        ###########################################################################################
        # ИСПОЛЬЗОВАТЬ ТОЛЬКО ДЛЯ НАСТРОЙКИ КАМЕР! ВКЛЮЧАТЬ ПО ОДНОДНОЙ! ВИСНЕТ ПО GPU
        #
        # cv2.imshow(f"Motion Detection - {camera_id.replace('cam', 'camera ')}", frame1)
        # if cv2.waitKey(25) & 0xFF == ord('q'):
        #     print(f"Окно для {camera_id.replace('cam', 'камеры ')} закрыто вручную.")
        #     stop_video_stream[camera_id] = True
        #     break
        #############################################################################################
        time.sleep(0.001)
        if stop_video_stream.get(camera_id, False):
            break

    cap.release()
    if out is not None:
        out.release()
    cv2.destroyAllWindows()
    # **ИСПРАВЛЕНО:** Заменили cam_id на camera_id
    status_cam(f"Видео {camera_id.replace('cam', 'камеры ')} остановлено.")