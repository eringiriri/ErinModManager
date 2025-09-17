import requests
from bs4 import BeautifulSoup
import time
import os
import csv
import sys
import re
from datetime import datetime

import chardet

# --- 設定 ---
from config import LOGS_DIR, CSV_FILENAME, CSV_ENCODING
from logger import get_logger

URL_FMT = "https://rimworld.2game.info/uploader_translation.php?id=&page={}"
OUTPUT_DIR = LOGS_DIR
# OUTPUT_FILENAMEはconfig.pyのCSV_FILENAMEを使用
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
TIMEOUT = 300

# --- ヘルパー関数 ---

def sanitize_text(text):
    """テキストをCSV出力用にサニタイズする"""
    if not text:
        return ""
    # 制御文字や改行文字を除去
    text = re.sub(r'[\r\n\t]', ' ', str(text))
    # 連続する空白を1つにまとめる
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def format_mod_update_date(mod_update_str, jp_upload_str):
    """
    Webサイトから取得した日本語の日付文字列を 'YYYY-MM-DD HH:MM:SS' 形式に変換します。
    """
    try:
        reference_year = datetime.strptime(jp_upload_str, '%Y-%m-%d %H:%M:%S').year
        
        if '年' in mod_update_str:
            match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日 @ (\d{1,2})時(\d{1,2})分', mod_update_str)
            if not match: return mod_update_str
            year, month, day, hour, minute = map(int, match.groups())
        else:
            match = re.search(r'(\d{1,2})月(\d{1,2})日 @ (\d{1,2})時(\d{1,2})分', mod_update_str)
            if not match: return mod_update_str
            year = reference_year
            month, day, hour, minute = map(int, match.groups())

        return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:00"
    except (ValueError, AttributeError, TypeError):
        return mod_update_str

# --- メイン処理 ---

def scrape_and_save_to_csv(pman=None):
    """
    サイトの全ページを巡回し、MOD情報を取得してCSVファイルに保存します。
    現在の処理状況をコンソールに詳細表示します。
    """
    logger = get_logger("TranslationScraper")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_filepath = os.path.join(OUTPUT_DIR, CSV_FILENAME)

    logger.info("翻訳リスト取得開始")
    if pman:
        pman.set_progress("データの取得を開始します...")
    else:
        print(f"データの取得を開始します...")
    print(f"出力ファイル: {os.path.abspath(output_filepath)}")

    processed_count = 0
    scanned_pages = 0
    try:
        with open(output_filepath, 'w', newline='', encoding=CSV_ENCODING) as csvfile:
            csv_writer = csv.writer(csvfile)
            
            header = ["Page Number", "File ID", "MOD ID", "MOD Name", "Mod-Update-Date", "JP-File-Upload-Date", "Size"]
            csv_writer.writerow(header)
            
            page_number = 0
            while True:
                url = URL_FMT.format(page_number)
                sys.stdout.write(f"\r{' ' * 100}\r")
                page_info = f"ページ {page_number + 1} の処理を開始"
                print(f"--- {page_info} ({url}) ---")
                if pman:
                    pman.set_progress(page_info)
                scanned_pages = page_number + 1

                try:
                    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
                    response.raise_for_status()
                    
                    # 文字コードを自動検出して設定
                    detected_encoding = chardet.detect(response.content)
                    if detected_encoding['encoding'] and detected_encoding['confidence'] > 0.7:
                        response.encoding = detected_encoding['encoding']
                        print(f"  文字コードを検出: {detected_encoding['encoding']} (信頼度: {detected_encoding['confidence']:.2f})")
                    else:
                        # 検出に失敗した場合はUTF-8を試す
                        response.encoding = 'utf-8'
                        print(f"  文字コード検出失敗、UTF-8を使用")
                        
                except requests.exceptions.RequestException as e:
                    print(f"\nエラー: ページ {page_number + 1} の取得に失敗しました: {e}", file=sys.stderr)
                    break

                soup = BeautifulSoup(response.text, 'html.parser')
                table = soup.find('table', class_='uploaderTable')

                if not table or not table.tbody:
                    print(f"ページ {page_number + 1} にデータテーブルが見つかりませんでした。最終ページと判断し、処理を終了します。")
                    break

                rows = table.tbody.find_all('tr')
                if not rows:
                    print(f"ページ {page_number + 1} にデータ行が見つかりませんでした。最終ページと判断し、処理を終了します。")
                    break

                is_data_found_on_page = False
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 6:
                        file_id = cells[0].text.strip()
                        if not file_id:
                            continue

                        is_data_found_on_page = True
                        file_info = f"File ID: {file_id} を処理中"
                        print(f"  - {file_info}...")
                        if pman:
                            pman.set_progress(f"ページ {page_number + 1} - {file_info}")

                        mod_cell = cells[1]
                        mod_id = sanitize_text(mod_cell.text.strip())
                        mod_name = sanitize_text(mod_cell.find('a', title=True)['title'].strip() if mod_cell.find('a', title=True) else "")
                        
                        mod_update_text = sanitize_text(cells[2].text.strip())
                        jp_upload_date = sanitize_text(cells[4].text.strip())
                        size = sanitize_text(cells[5].text.strip())
                        
                        mod_update_date_formatted = format_mod_update_date(mod_update_text, jp_upload_date)
                        
                        csv_writer.writerow([
                            page_number + 1, file_id, mod_id, mod_name, 
                            mod_update_date_formatted, jp_upload_date, size
                        ])
                        processed_count += 1
                
                if not is_data_found_on_page:
                    print(f"ページ {page_number + 1} で有効なデータが検出されませんでした。処理を終了します。")
                    break

                page_number += 1
                time.sleep(0.5)

    except (KeyboardInterrupt, SystemExit):
        print("\n\n処理がユーザーによって中断されました。")
    except Exception as e:
        print(f"\n予期せぬエラーが発生しました: {e}", file=sys.stderr)
    finally:
        completion_info = f"処理完了 - スキャン: {scanned_pages}ページ, 取得: {processed_count}件"
        logger.info(f"翻訳リスト取得完了: {scanned_pages}ページ, {processed_count}件")
        print(f"\n--- 処理完了 ---")
        print(f"スキャンした総ページ数: {scanned_pages} ページ")
        print(f"取得した総データ件数: {processed_count} 件")
        print(f"データは {os.path.abspath(output_filepath)} に保存されました。")
        if pman:
            pman.set_progress(completion_info)

if __name__ == '__main__':
    scrape_and_save_to_csv()