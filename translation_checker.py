import os
import csv
import requests
from bs4 import BeautifulSoup

from config import LOGS_DIR
from translation_scraper import format_mod_update_date

# chardetの可用性チェック
try:
    import chardet
    CHARDET_AVAILABLE = True
except ImportError:
    CHARDET_AVAILABLE = False


class TranslationChecker:
    """最新翻訳チェック機能を管理するクラス"""
    
    def __init__(self, pman):
        self.pman = pman
        self.csv_file = os.path.join(LOGS_DIR, "rimworld_translation_list.csv")
        
    def check_for_updates(self):
        """ウェブサイトの最新投稿をチェックして、CSVにないFile IDを追加"""
        try:
            self.pman.set_status("最新翻訳をチェック中...")
            
            # 既存のCSVファイルからFile IDを取得
            existing_file_ids = set()
            csv_exists = os.path.exists(self.csv_file)
            
            if csv_exists:
                with open(self.csv_file, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    existing_file_ids = {row['File ID'] for row in reader}
                self.pman.set_progress(f"既存のCSVファイルから {len(existing_file_ids)} 件のFile IDを読み込み")
                
                # CSVが存在する場合：0ページ目のみチェック（効率的）
                self.pman.set_status("ウェブサイトの最新投稿をチェック中...")
                new_translations = self._get_latest_translations()
                
                if not new_translations:
                    self.pman.popup_info("最新の翻訳投稿が見つかりませんでした。")
                    return
                
                # 新しいFile IDを検出
                new_file_ids = {t['File ID'] for t in new_translations}
                added_file_ids = new_file_ids - existing_file_ids
                
                if not added_file_ids:
                    self.pman.popup_info("新しい翻訳投稿はありませんでした。\n\n最新の投稿はすべてCSVに登録済みです。\nCSVファイルは最新の状態です。")
                    return
                
                # 新しい翻訳をCSVに追加
                self.pman.set_progress(f"新しい翻訳 {len(added_file_ids)} 件をCSVに追加中...")
                self._append_to_csv(new_translations, added_file_ids)
                
                # 適用可能な翻訳をチェック
                self._check_applicable_translations(new_translations, added_file_ids)
                
            else:
                # CSVが存在しない場合：全ページを取得（新規作成）
                self.pman.set_status("CSVファイルが存在しないため、全翻訳リストを取得します...")
                from translation_scraper import scrape_and_save_to_csv
                scrape_and_save_to_csv(self.pman)
                self.pman.popup_info("翻訳リストの新規作成が完了しました。\n「一括日本語ファイル適用」ボタンで適用できます。")
            
        except Exception as e:
            self.pman.set_status("最新翻訳チェック失敗")
            self.pman.popup_error(f"最新翻訳チェック中にエラーが発生しました。\n{e}")
    
    def _get_latest_translations(self):
        """ウェブサイトの最新投稿（0ページ目）を取得"""
        url = "https://rimworld.2game.info/uploader_translation.php?id=&page=0"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 文字コードを自動検出
            if CHARDET_AVAILABLE:
                detected_encoding = chardet.detect(response.content)
                if detected_encoding['encoding'] and detected_encoding['confidence'] > 0.7:
                    response.encoding = detected_encoding['encoding']
                else:
                    response.encoding = 'utf-8'
            else:
                response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', class_='uploaderTable')
            
            if not table or not table.tbody:
                return []
            
            rows = table.tbody.find_all('tr')
            translations = []
            
            for i, row in enumerate(rows):
                cells = row.find_all('td')
                if len(cells) >= 6:
                    file_id = cells[0].text.strip()
                    if not file_id:
                        continue
                    
                    # 進捗表示
                    self.pman.set_progress(f"翻訳データを解析中... ({i+1}/{len(rows)}) File ID: {file_id}")
                    
                    mod_cell = cells[1]
                    mod_id = mod_cell.text.strip()
                    mod_name = mod_cell.find('a', title=True)['title'].strip() if mod_cell.find('a', title=True) else ""
                    
                    mod_update_text = cells[2].text.strip()
                    jp_upload_date = cells[4].text.strip()
                    size = cells[5].text.strip()
                    
                    # 日付フォーマット
                    mod_update_date_formatted = format_mod_update_date(mod_update_text, jp_upload_date)
                    
                    translations.append({
                        'File ID': file_id,
                        'MOD ID': mod_id,
                        'MOD Name': mod_name,
                        'Mod-Update-Date': mod_update_date_formatted,
                        'JP-File-Upload-Date': jp_upload_date,
                        'Size': size
                    })
            
            return translations
            
        except Exception as e:
            self.pman.popup_error(f"最新投稿の取得に失敗しました。\n{e}")
            return []
    
    def _append_to_csv(self, new_translations, added_file_ids):
        """新しい翻訳をCSVファイルに追加"""
        # 追加する翻訳のみをフィルタリング
        translations_to_add = [t for t in new_translations if t['File ID'] in added_file_ids]
        
        # CSVファイルに追加
        with open(self.csv_file, 'a', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            for translation in translations_to_add:
                writer.writerow([
                    0,  # Page Number (最新投稿なので0)
                    translation['File ID'],
                    translation['MOD ID'],
                    translation['MOD Name'],
                    translation['Mod-Update-Date'],
                    translation['JP-File-Upload-Date'],
                    translation['Size']
                ])
    
    def _check_applicable_translations(self, new_translations, added_file_ids):
        """追加された翻訳のうち適用可能なものをチェック"""
        # インストール済みMOD取得
        from auto_japanizer import AutoJapanizer
        auto_jp = AutoJapanizer(self.pman)
        installed_mods = auto_jp.get_installed_mods()
        
        if not installed_mods:
            self.pman.popup_warning("インストール済みのMODが見つかりませんでした。")
            return
        
        # 適用可能な翻訳を検索
        applicable_new = []
        processed_mod_ids = set()
        
        for translation in new_translations:
            if translation['File ID'] not in added_file_ids:
                continue
                
            mod_id = translation['MOD ID']
            if mod_id in installed_mods and mod_id not in processed_mod_ids:
                applicable_new.append({
                    'mod_name': translation['MOD Name'],
                    'mod_id': mod_id,
                    'file_id': translation['File ID'],
                    'upload_date': translation['JP-File-Upload-Date']
                })
                processed_mod_ids.add(mod_id)
        
        # 結果報告
        if applicable_new:
            message = f"新しい日本語化ファイルが見つかりました！\n\n"
            message += f"新規追加: {len(added_file_ids)}件\n"
            message += f"適用可能: {len(applicable_new)}件\n\n"
            message += "適用可能なMOD:\n"
            for item in applicable_new[:10]:
                message += f"・{item['mod_name']} (ID: {item['mod_id']})\n"
            if len(applicable_new) > 10:
                message += f"... 他 {len(applicable_new) - 10}件\n"
            message += "\n「一括日本語ファイル適用」ボタンで適用できます。"
            
            self.pman.set_status("新しい翻訳ファイルを発見！")
            self.pman.popup_info(message)
        else:
            message = f"新しい翻訳を {len(added_file_ids)} 件追加しました。\n\n"
            message += f"適用可能な新しい翻訳: 0件\n\n"
            message += "現在インストール済みのMODに対応する新しい翻訳はありませんでした。"
            
            self.pman.set_status("最新翻訳チェック完了")
            self.pman.popup_info(message)


def check_translation_updates(pman):
    """最新翻訳チェックのエントリーポイント"""
    checker = TranslationChecker(pman)
    checker.check_for_updates()
