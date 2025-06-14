from ytmusicapi import YTMusic
import pandas as pd
import tkinter as tk
from tkinter import filedialog
import os
import sys
import re
import time
from fuzzywuzzy import fuzz, process

import ctypes

ctypes.windll.shcore.SetProcessDpiAwareness(True)

if os.name == 'nt':
    os.system('color')


YELLOW = '\033[93m'
RED = '\033[91m'
GREEN = '\033[92m'
BLUE = '\033[94m'
RESET = '\033[0m'


class PlaylistTransfer:
    def __init__(self):

        self.FUZZY_THRESHOLD_TITLE = 70
        self.FUZZY_THRESHOLD_ARTIST = 65
        self.FUZZY_THRESHOLD_ALBUM = 60
        self.DURATION_TOLERANCE = 15000


        try:
            self.ytmusic = YTMusic('headers_auth.json')
            print(GREEN + "YTMusic успешно инициализирован" + RESET)
        except Exception as e:
            print(RED + f"Ошибка при инициализации YTMusic: {e}" + RESET)
            sys.exit(1)

    def clean_text(self, text):
        if not text:
            return ""

        text = re.sub(r'\s*\([^)]*\)', '', text)
        text = re.sub(r'\s*\[[^\]]*\]', '', text)
        text = re.sub(r'\s*-\s*remaster(ed)?.*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*-\s*live.*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bfeat\.?\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bft\.?\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip().lower()

        return text

    def advanced_similarity(self, str1, str2):

        if not str1 or not str2:
            return 0

        str1_clean = self.clean_text(str1)
        str2_clean = self.clean_text(str2)


        ratio = fuzz.ratio(str1_clean, str2_clean)
        partial_ratio = fuzz.partial_ratio(str1_clean, str2_clean)
        token_sort_ratio = fuzz.token_sort_ratio(str1_clean, str2_clean)
        token_set_ratio = fuzz.token_set_ratio(str1_clean, str2_clean)


        return max(ratio, partial_ratio, token_sort_ratio, token_set_ratio)

    def generate_search_queries(self, track_name, artist_name, album_name=""):
        queries = []

        queries.append(f"{track_name} {artist_name}")

        if album_name:
            queries.append(f"{track_name} {artist_name} {album_name}")

        queries.append(track_name)

        clean_track = self.clean_text(track_name)
        clean_artist = self.clean_text(artist_name)
        if clean_track and clean_artist:
            queries.append(f"{clean_track} {clean_artist}")

        queries.append(f'"{track_name}" {artist_name}')

        return list(dict.fromkeys(queries))

    def search_track_comprehensive(self, track_name, artist_name, album_name="", duration_ms=0):
        queries = self.generate_search_queries(track_name, artist_name, album_name)

        best_match = None
        best_score = 0
        search_attempts = 0

        for query in queries:
            if search_attempts >= 10:
                break

            try:
                results = self.ytmusic.search(query, filter="songs", limit=5)
                match = self.evaluate_results(results, track_name, artist_name, album_name, duration_ms, "song")

                if match and match['score'] > best_score:
                    best_match = match
                    best_score = match['score']

                if best_score > 85:
                    break

                time.sleep(0.1)
                results = self.ytmusic.search(query, filter="videos", limit=3)
                match = self.evaluate_results(results, track_name, artist_name, album_name, duration_ms, "video")

                if match and match['score'] > best_score:
                    best_match = match
                    best_score = match['score']

                search_attempts += 2
                time.sleep(0.1)

            except Exception as e:
                print(YELLOW + f"Ошибка поиска для запроса '{query}': {e}" + RESET)
                continue

        return best_match if best_score > 50 else None

    def evaluate_results(self, results, track_name, artist_name, album_name, duration_ms, result_type):
        best_match = None
        best_score = 0

        for result in results:
            if result.get('resultType') not in ['song', 'video']:
                continue

            try:
                result_title = result.get('title', '')
                result_artists = result.get('artists', [])
                result_artist = ', '.join([artist['name'] for artist in result_artists]) if result_artists else ''
                result_album = ''

                if result.get('album'):
                    result_album = result['album'].get('name', '')

                result_duration = result.get('duration_seconds', 0) * 1000
                track_id = result.get('videoId')

                if not track_id:
                    continue

                title_score = self.advanced_similarity(track_name, result_title)
                artist_score = self.advanced_similarity(artist_name, result_artist)
                album_score = self.advanced_similarity(album_name, result_album) if album_name and result_album else 70

                duration_score = 100
                if duration_ms and result_duration:
                    duration_diff = abs(duration_ms - result_duration)
                    if duration_diff > self.DURATION_TOLERANCE * 2:
                        duration_score = 0
                    elif duration_diff > self.DURATION_TOLERANCE:
                        duration_score = 50

                total_score = (title_score * 0.4 +
                               artist_score * 0.4 +
                               album_score * 0.1 +
                               duration_score * 0.1)

                if result_type == "song":
                    total_score += 5

                print(BLUE + f"  Оценка: {result_title} by {result_artist} - "
                             f"Title: {title_score:.1f}, Artist: {artist_score:.1f}, "
                             f"Album: {album_score:.1f}, Duration: {duration_score:.1f}, "
                             f"Total: {total_score:.1f}" + RESET)

                if total_score > best_score and self.meets_minimum_criteria(title_score, artist_score, total_score):
                    best_match = {
                        'track_id': track_id,
                        'title': result_title,
                        'artist': result_artist,
                        'album': result_album,
                        'duration': result_duration,
                        'score': total_score,
                        'type': result_type
                    }
                    best_score = total_score

            except Exception as e:
                print(YELLOW + f"Ошибка при обработке результата: {e}" + RESET)
                continue

        return best_match

    def meets_minimum_criteria(self, title_score, artist_score, total_score):
        return (title_score >= self.FUZZY_THRESHOLD_TITLE and
                artist_score >= self.FUZZY_THRESHOLD_ARTIST and
                total_score >= 50)

    def transfer_playlist(self, csv_file_path):
        playlist_name = os.path.splitext(os.path.basename(csv_file_path))[0]
        print(f"Название плейлиста будет: {playlist_name}")

        try:
            df = pd.read_csv(csv_file_path)
            print(f"CSV-файл успешно прочитан, найдено {len(df)} треков")
        except Exception as e:
            print(RED + f"Ошибка при чтении CSV-файла: {e}" + RESET)
            return

        df = df.drop_duplicates(subset=['Track Name', 'Artist Name(s)'])
        print(f"После удаления дубликатов осталось {len(df)} треков")

        try:
            playlist_id = self.ytmusic.create_playlist(
                title=playlist_name,
                description=f"Playlist created from {os.path.basename(csv_file_path)}",
                privacy_status="PRIVATE"
            )
            print(GREEN + f"Создан плейлист: {playlist_name} (ID: {playlist_id})" + RESET)
        except Exception as e:
            print(RED + f"Ошибка при создании плейлиста: {e}" + RESET)
            return

        successful_tracks = []
        failed_tracks = []
        track_ids_to_add = []

        for index, row in df.iterrows():
            track_name = row['Track Name']
            artist_name = row['Artist Name(s)']
            album_name = row.get('Album Name', '')
            duration_ms = row.get('Duration (ms)', 0)

            print(f"\n[{index + 1}/{len(df)}] Поиск: {track_name} by {artist_name}")

            try:
                match = self.search_track_comprehensive(track_name, artist_name, album_name, duration_ms)

                if match:
                    track_ids_to_add.append(match['track_id'])
                    successful_tracks.append({
                        'original': f"{track_name} by {artist_name}",
                        'found': f"{match['title']} by {match['artist']}",
                        'score': match['score'],
                        'type': match['type']
                    })
                    print(GREEN + f"✓ Найден: {match['title']} by {match['artist']} "
                                  f"(score: {match['score']:.1f}, {match['type']})" + RESET)
                else:
                    failed_tracks.append(f"{track_name} by {artist_name}: Не найден подходящий результат")
                    print(RED + f"✗ Не найден: {track_name} by {artist_name}" + RESET)

            except Exception as e:
                failed_tracks.append(f"{track_name} by {artist_name}: Ошибка поиска ({e})")
                print(RED + f"✗ Ошибка при поиске '{track_name}': {e}" + RESET)

        print(YELLOW + "Завершение текущего сеанса YTMusic..." + RESET)
        self.ytmusic = None
        try:
            self.ytmusic = YTMusic('headers_auth.json')
            print(GREEN + "Новый сеанс YTMusic успешно инициализирован" + RESET)
        except Exception as e:
            print(RED + f"Ошибка при инициализации нового сеанса YTMusic: {e}" + RESET)


        if track_ids_to_add:
            print(f"\nДобавление {len(track_ids_to_add)} треков в плейлист...")
            added_count = 0

            for i, track_id in enumerate(track_ids_to_add):
                try:
                    self.ytmusic.add_playlist_items(playlist_id, [track_id])
                    added_count += 1
                    print(f"Добавлен трек {i + 1}/{len(track_ids_to_add)}")
                    time.sleep(0.1)
                except Exception as e:
                    track_info = successful_tracks[i]['original']
                    failed_tracks.append(f"{track_info}: Ошибка добавления ({e})")
                    print(RED + f"Ошибка при добавлении трека: {e}" + RESET)

            print(GREEN + f"Успешно добавлено {added_count} из {len(track_ids_to_add)} треков" + RESET)

        self.save_report(playlist_name, successful_tracks, failed_tracks)

        print(f"\nСтатистика:")
        print(
            f"Успешно найдено и добавлено: {len(successful_tracks) - len([f for f in failed_tracks if 'Ошибка добавления' in f])}")
        print(f"Не найдено: {len([f for f in failed_tracks if 'Не найден' in f])}")
        print(f"Ошибки: {len([f for f in failed_tracks if 'Ошибка' in f])}")

    def save_report(self, playlist_name, successful_tracks, failed_tracks):
        report_file = f"transfer_report_{playlist_name}.txt"

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"Отчет о переносе плейлиста: {playlist_name}\n")
            f.write("=" * 50 + "\n\n")

            f.write("УСПЕШНО НАЙДЕННЫЕ ТРЕКИ:\n")
            f.write("-" * 30 + "\n")
            for track in successful_tracks:
                f.write(f"Оригинал: {track['original']}\n")
                f.write(f"Найден: {track['found']}\n")
                f.write(f"Точность: {track['score']:.1f}% ({track['type']})\n\n")

            f.write("\nНЕУДАЧНЫЕ ТРЕКИ:\n")
            f.write("-" * 20 + "\n")
            for track in failed_tracks:
                f.write(f"{track}\n")

        print(f"Подробный отчет сохранен в {report_file}")


def main():
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
        return

    transfer = PlaylistTransfer()
    transfer.transfer_playlist(csv_file_path)

    print(GREEN + "Процесс завершён!" + RESET)


if __name__ == "__main__":
    main()