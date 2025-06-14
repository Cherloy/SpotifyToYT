from ytmusicapi import YTMusic
import pandas as pd
import tkinter as tk
from tkinter import filedialog
import os
import sys

# Активация ANSI-кодов в Windows
if os.name == 'nt':
    os.system('color')

# Определение ANSI-кодов для цветов
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

# Инициализация YTMusic
try:
    ytmusic = YTMusic('headers_auth.json')
    print("YTMusic успешно инициализирован")
except Exception as e:
    print(f"Ошибка при инициализации YTMusic: {e}")
    sys.exit(1)

# Диалоговое окно для выбора CSV
root = tk.Tk()
root.withdraw()
print("Открывается диалоговое окно для выбора CSV-файла...")
csv_file_path = filedialog.askopenfilename(
    title="Выберите CSV-файл",
    filetypes=[("CSV files", "*.csv")]
)
root.destroy()

if not csv_file_path:
    print("Файл не выбран. Программа завершена.")
    sys.exit(1)

# Извлечение имени плейлиста из файла
playlist_name = os.path.splitext(os.path.basename(csv_file_path))[0]
print(f"Название плейлиста будет: {playlist_name}")

# Чтение CSV
try:
    df = pd.read_csv(csv_file_path)
    print(f"CSV-файл успешно прочитан, найдено {len(df)} треков")
except FileNotFoundError:
    print(f"Файл {csv_file_path} не найден.")
    sys.exit(1)
except Exception as e:
    print(f"Ошибка при чтении CSV-файла: {e}")
    sys.exit(1)

# Удаление дубликатов
df = df.drop_duplicates(subset=['Track Name', 'Artist Name(s)'])
print(f"После удаления дубликатов осталось {len(df)} треков")

# Создание плейлиста
try:
    playlist_id = ytmusic.create_playlist(
        title=playlist_name,
        description=f"Playlist created from {os.path.basename(csv_file_path)}",
        privacy_status="PRIVATE"
    )
    print(f"Создан плейлист: {playlist_name} (ID: {playlist_id})")
except Exception as e:
    print(f"Ошибка при создании плейлиста: {e}")
    sys.exit(1)

# Создание файла для записи пропущенных треков
skipped_tracks_file = '../skipped_tracks.txt'
with open(skipped_tracks_file, 'w', encoding='utf-8') as f:
    f.write("Пропущенные треки:\n")

# Списки для хранения треков
failed_tracks = []
successfully_added_tracks = []

# Поиск треков и добавление в плейлист
track_ids = []
track_info = {}
DURATION_TOLERANCE = 10000  # Допуск ±10 секунд (в миллисекундах)
for index, row in df.iterrows():
    track_name = row['Track Name']
    artist_name = row['Artist Name(s)']
    album_name = row.get('Album Name', '')
    duration_ms = row.get('Duration (ms)', 0)
    query = f"{track_name} {artist_name} {album_name}".strip()

    try:
        # Первый поиск: только песни
        search_results = ytmusic.search(query, filter="songs", limit=3)
        found = False
        for result in search_results:
            if result.get('resultType') != 'song':
                continue
            track_id = result.get('videoId')
            result_title = result.get('title', '')
            result_artist = ', '.join([artist['name'] for artist in result.get('artists', [])])
            result_album = result.get('album', {}).get('name', '') if result.get('album') else ''
            result_duration = result.get('duration_seconds', 0) * 1000

            # Проверка соответствия названия трека
            if track_name.lower() not in result_title.lower():
                print(YELLOW + f"Трек пропущен (несоответствие названия): {track_name} by {artist_name} "
                      f"(Найдено: {result_title})" + RESET)
                with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                    f.write(f"{track_name} by {artist_name} (Несоответствие названия: {result_title})\n")
                failed_tracks.append(f"{track_name} by {artist_name}: Несоответствие названия (Найдено: {result_title})")
                continue

            # Проверка соответствия исполнителя
            if artist_name.lower() not in result_artist.lower():
                print(YELLOW + f"Трек пропущен (несоответствие исполнителя): {track_name} by {artist_name} "
                      f"(Найдено: {result_artist})" + RESET)
                with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                    f.write(f"{track_name} by {artist_name} (Несоответствие исполнителя: {result_artist})\n")
                failed_tracks.append(f"{track_name} by {artist_name}: Несоответствие исполнителя (Найдено: {result_artist})")
                continue

            # Проверка длительности
            if duration_ms and abs(duration_ms - result_duration) > DURATION_TOLERANCE:
                print(YELLOW + f"Трек пропущен (несоответствие длительности): {track_name} by {artist_name} "
                      f"(CSV: {duration_ms/1000}s, найдено: {result_duration/1000}s)" + RESET)
                with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                    f.write(f"{track_name} by {artist_name} (Несоответствие длительности: CSV {duration_ms/1000}s, найдено {result_duration/1000}s)\n")
                failed_tracks.append(f"{track_name} by {artist_name}: Несоответствие длительности (CSV: {duration_ms/1000}s, найдено: {result_duration/1000}s)")
                continue

            # Проверка альбома
            if album_name and result_album and album_name.lower() not in result_album.lower():
                print(YELLOW + f"Трек пропущен (несоответствие альбома): {track_name} by {artist_name} "
                      f"(CSV: {album_name}, найдено: {result_album})" + RESET)
                with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                    f.write(f"{track_name} by {artist_name} (Несоответствие альбома: CSV {album_name}, найдено {result_album})\n")
                failed_tracks.append(f"{track_name} by {artist_name}: Несоответствие альбома (CSV: {album_name}, найдено: {result_album})")
                continue

            track_ids.append(track_id)
            track_info[track_id] = {'name': track_name, 'artist': artist_name}
            print(f"Найден трек: {track_name} by {artist_name} (ID: {track_id}, альбом: {result_album}, "
                  f"длительность: {result_duration/1000}s)")
            found = True
            break

        # Если трек не найден среди песен, ищем среди видео
        if not found:
            print(YELLOW + f"Трек не найден среди песен, ищем среди видео: {track_name} by {artist_name}" + RESET)
            search_results = ytmusic.search(query, limit=3)  # Поиск без фильтра
            for result in search_results:
                if result.get('resultType') != 'video':
                    continue
                track_id = result.get('videoId')
                result_title = result.get('title', '')
                result_artist = ', '.join([artist['name'] for artist in result.get('artists', [])]) if result.get('artists') else ''
                result_duration = result.get('duration_seconds', 0) * 1000

                # Проверка соответствия названия трека
                if track_name.lower() not in result_title.lower():
                    print(YELLOW + f"Видео пропущено (несоответствие названия): {track_name} by {artist_name} "
                          f"(Найдено: {result_title})" + RESET)
                    with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                        f.write(f"{track_name} by {artist_name} (Несоответствие названия видео: {result_title})\n")
                    failed_tracks.append(f"{track_name} by {artist_name}: Несоответствие названия видео (Найдено: {result_title})")
                    continue

                # Проверка соответствия исполнителя
                if artist_name and result_artist and artist_name.lower() not in result_artist.lower():
                    print(YELLOW + f"Видео пропущено (несоответствие исполнителя): {track_name} by {artist_name} "
                          f"(Найдено: {result_artist})" + RESET)
                    with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                        f.write(f"{track_name} by {artist_name} (Несоответствие исполнителя видео: {result_artist})\n")
                    failed_tracks.append(f"{track_name} by {artist_name}: Несоответствие исполнителя видео (Найдено: {result_artist})")
                    continue

                # Проверка длительности
                if duration_ms and abs(duration_ms - result_duration) > DURATION_TOLERANCE:
                    print(YELLOW + f"Видео пропущено (несоответствие длительности): {track_name} by {artist_name} "
                          f"(CSV: {duration_ms/1000}s, найдено: {result_duration/1000}s)" + RESET)
                    with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                        f.write(f"{track_name} by {artist_name} (Несоответствие длительности видео: CSV {duration_ms/1000}s, найдено {result_duration/1000}s)\n")
                    failed_tracks.append(f"{track_name} by {artist_name}: Несоответствие длительности видео (CSV: {duration_ms/1000}s, найдено: {result_duration/1000}s)")
                    continue

                track_ids.append(track_id)
                track_info[track_id] = {'name': track_name, 'artist': artist_name}
                print(f"Найдено видео: {track_name} by {artist_name} (ID: {track_id}, длительность: {result_duration/1000}s)")
                found = True
                break

        if not found:
            print(YELLOW + f"Трек или видео не найдены или не соответствуют критериям: {track_name} by {artist_name}" + RESET)
            with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
                f.write(f"{track_name} by {artist_name} (Не найден или не соответствует критериям)\n")
            failed_tracks.append(f"{track_name} by {artist_name}: Не найден или не соответствует критериям")
    except Exception as e:
        print(YELLOW + f"Ошибка при поиске трека '{track_name}': {e}" + RESET)
        with open(skipped_tracks_file, 'a', encoding='utf-8') as f:
            f.write(f"{track_name} by {artist_name} (Ошибка поиска: {e})\n")
        failed_tracks.append(f"{track_name} by {artist_name}: Ошибка поиска ({e})")

# Вывод собранных track_ids
print(f"Собранные track_ids: {track_ids}")

# Добавление треков
if track_ids:
    for track_id in track_ids:
        try:
            ytmusic.add_playlist_items(playlist_id, [track_id])
            track_name = track_info[track_id]['name']
            artist_name = track_info[track_id]['artist']
            print(f"Добавлен трек: {track_name} by {artist_name}")
            successfully_added_tracks.append(f"{track_name} by {artist_name}")
        except Exception as e:
            track_name = track_info.get(track_id, {'name': 'Неизвестно'})['name']
            artist_name = track_info.get(track_id, {'artist': 'Неизвестно'})['artist']
            if "HTTP 409" in str(e):
                print(RED + f"Не удалось добавить трек: {track_name} by {artist_name}. "
                      f"Возможно, трек уже в плейлисте или недоступен." + RESET)
                failed_tracks.append(f"{track_name} by {artist_name}: Не удалось добавить (HTTP 409, возможно, уже в плейлисте или недоступен)")
            else:
                print(RED + f"Ошибка при добавлении трека {track_name} by {artist_name}: {e}" + RESET)
                print(RED + f"Детали ошибки: {str(e.__dict__)}" + RESET)
                failed_tracks.append(f"{track_name} by {artist_name}: Ошибка добавления ({e})")
else:
    print(YELLOW + "Ни один трек не был добавлен, так как ничего не найдено." + RESET)

# Запись списка неудачных треков в файл, исключая успешно добавленные
failed_tracks_file = '../failed_tracks.txt'
with open(failed_tracks_file, 'w', encoding='utf-8') as f:
    filtered_failed_tracks = [track for track in failed_tracks if not any(success in track for success in successfully_added_tracks)]
    if filtered_failed_tracks:
        for track in filtered_failed_tracks:
            f.write(f"{track}\n")
    else:
        f.write("Все треки успешно обработаны.\n")

print(f"Список неудачных треков сохранён в {failed_tracks_file}")
print("Процесс завершен.")