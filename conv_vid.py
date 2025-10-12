# конвектор
import time
from moviepy import VideoFileClip
import os


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
            if not os.path.exists(archive_dir):
                try:
                    os.mkdir(archive_dir)
                except Exception as e:
                    print(f"Не удалось создать папку архива: {e}")
                    continue

            for file in files:
                vide_file = os.path.join(root, file)
                if (now - os.path.getctime(vide_file)) / (24 * 3600) >= days:
                    if vide_file.lower().endswith('.mp4'):
                        print(f'Перекодирование файла\n{file}')
                        try:
                            clip = VideoFileClip(vide_file)
                            new_filepath = os.path.join(archive_dir, file.replace('.mp4', '_conv.mp4'))
                            # Параметр threads=1 для использования одного ядра (можно менять или вообзе загнать в переменную
                            clip.write_videofile(new_filepath, audio=False, codec="libx264", threads=1)
                            clip.close()
                            print(f'Архивация {file} завершена.')
                            os.remove(vide_file)
                        except Exception as e:
                            print(f'Ошибка кодировки файла {file}: {e}')

