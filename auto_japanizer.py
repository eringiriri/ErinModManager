import os
import csv
import json
import shutil
import logging
import time
from datetime import datetime
from collections import defaultdict

from config import MODS_DIR, LOCAL_MODS_DIR, LOGS_DIR, TMP_DIR, OLD_DIR, LANG_DIR_NAME, JP_DIR_NAME
from utils import sanitize_filename, get_mod_name_from_xml, force_remove, find_japanese_dir
from downloader import download_zip, is_archive_file, extract_archive
from translation_scraper import scrape_and_save_to_csv


class AutoJapanizer:
    """一括日本語化機能を管理するクラス"""
    
    def __init__(self, pman):
        self.pman = pman
        self.logger = self._setup_logger()
        self.status_file = os.path.join(LOGS_DIR, "japanization_status.json")
        self.csv_file = os.path.join(LOGS_DIR, "rimworld_translation_list.csv")
        
    def _setup_logger(self):
        """ログ設定"""
        os.makedirs(LOGS_DIR, exist_ok=True)
        log_file = os.path.join(LOGS_DIR, f"auto_japanizer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        logger = logging.getLogger("AutoJapanizer")
        if logger.hasHandlers():
            logger.handlers.clear()
            
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(log_file, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger
        
    def load_japanization_status(self):
        """適用済みFile IDの状態を読み込む"""
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self.logger.warning("ステータスファイルの読み込みに失敗、新規作成します")
        return {}
        
    def save_japanization_status(self, status):
        """適用済みFile IDの状態を保存する"""
        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"ステータスファイルの保存に失敗: {e}")
            
    def load_translation_list(self):
        """翻訳リストCSVを読み込む"""
        if not os.path.exists(self.csv_file):
            self.logger.error(f"翻訳リストファイルが見つかりません: {self.csv_file}")
            return []
            
        translations = []
        try:
            with open(self.csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    translations.append({
                        'file_id': row['File ID'],
                        'mod_id': row['MOD ID'],
                        'mod_name': row['MOD Name'],
                        'jp_upload_date': row['JP-File-Upload-Date']
                    })
        except Exception as e:
            self.logger.error(f"翻訳リストの読み込みに失敗: {e}")
            return []
            
        self.logger.info(f"翻訳リストを読み込みました: {len(translations)}件")
        return translations
        
    def get_installed_mods(self):
        """インストール済みMODの一覧を取得"""
        installed_mods = {}
        
        for mod_type, mod_dir in [("Workshop", MODS_DIR), ("Local", LOCAL_MODS_DIR)]:
            if not os.path.isdir(mod_dir):
                continue
                
            for folder_name in os.listdir(mod_dir):
                mod_path = os.path.join(mod_dir, folder_name)
                if os.path.isdir(mod_path):
                    sanitized_id = sanitize_filename(folder_name)
                    display_name = get_mod_name_from_xml(mod_path) or folder_name
                    
                    installed_mods[sanitized_id] = {
                        'mod_id': sanitized_id,
                        'path': mod_path,
                        'type': mod_type,
                        'display_name': display_name,
                        'original_folder': folder_name
                    }
                    
        self.logger.info(f"インストール済みMOD: {len(installed_mods)}件")
        return installed_mods
        
    def find_applicable_translations(self, installed_mods, translations):
        """適用可能な翻訳を検索（CSVの上位を優先）"""
        applicable = []
        status = self.load_japanization_status()
        processed_mod_ids = set()  # 既に処理したMOD IDを記録
        
        for translation in translations:
            mod_id = translation['mod_id']
            file_id = translation['file_id']
            
            # MODがインストールされているかチェック
            if mod_id not in installed_mods:
                continue
                
            # 同じMOD IDが既に処理済みの場合はスキップ（CSVの上位を優先）
            if mod_id in processed_mod_ids:
                self.logger.info(f"MOD {mod_id} は既に新しい翻訳が検出済み、古い翻訳をスキップ (File ID: {file_id})")
                continue
                
            # 既に適用済みかチェック
            mod_status = status.get(mod_id, {})
            if mod_status.get('applied_file_id') == file_id:
                self.logger.info(f"MOD {mod_id} は既に最新の翻訳が適用済み (File ID: {file_id})")
                processed_mod_ids.add(mod_id)  # 適用済みでも記録して重複を防ぐ
                continue
                
            # 新しい翻訳として追加
            applicable.append({
                'translation': translation,
                'mod_info': installed_mods[mod_id]
            })
            processed_mod_ids.add(mod_id)  # 処理済みとして記録
            
        self.logger.info(f"適用可能な翻訳: {len(applicable)}件")
        return applicable
        
            
    def _analyze_existing_csv(self):
        """既存のCSVファイルを分析して適用可能な翻訳をチェック"""
        try:
            # 既存の翻訳リストを読み込み
            translations = self.load_translation_list()
            if not translations:
                self.pman.popup_error("翻訳リストの読み込みに失敗しました。")
                return
                
            # インストール済みMOD取得
            installed_mods = self.get_installed_mods()
            if not installed_mods:
                self.pman.popup_warning("インストール済みのMODが見つかりませんでした。")
                return
                
            # 適用可能な翻訳検索
            applicable = self.find_applicable_translations(installed_mods, translations)
            
            if applicable:
                message = f"適用可能な日本語化ファイルが見つかりました！\n\n"
                message += f"適用可能: {len(applicable)}件\n\n"
                message += "適用可能なMOD:\n"
                for item in applicable[:10]:  # 最初の10件のみ表示
                    mod_name = item['mod_info']['display_name']
                    mod_id = item['translation']['mod_id']
                    message += f"・{mod_name} (ID: {mod_id})\n"
                if len(applicable) > 10:
                    message += f"... 他 {len(applicable) - 10}件\n"
                message += "\n「一括日本語ファイル適用」ボタンで適用できます。"
                
                self.pman.set_status("適用可能な翻訳ファイルを発見！")
                self.pman.popup_info(message)
            else:
                message = f"翻訳リストを確認しました。\n\n"
                message += f"適用可能な新しい翻訳: 0件\n\n"
                message += "現在インストール済みのMODに対応する新しい翻訳はありませんでした。"
                
                self.pman.set_status("翻訳リスト確認完了")
                self.pman.popup_info(message)
                
            self.logger.info(f"既存CSV分析完了: 適用可能 {len(applicable)}件")
            
        except Exception as e:
            self.logger.exception(f"既存CSV分析中にエラー: {e}")
            self.pman.set_status("翻訳リスト確認失敗")
            self.pman.popup_error(f"翻訳リストの確認中にエラーが発生しました。\n{e}")
        
    def apply_japanization(self, translation_info):
        """個別のMODに日本語化を適用"""
        translation = translation_info['translation']
        mod_info = translation_info['mod_info']
        
        mod_id = translation['mod_id']
        file_id = translation['file_id']
        mod_name = translation['mod_name']
        
        self.logger.info(f"日本語化適用開始: {mod_name} (MOD ID: {mod_id}, File ID: {file_id})")
        self.pman.set_progress(f"適用中: {mod_name} (File ID: {file_id})")
        
        try:
            # ダウンロードURL構築
            download_url = f"https://rimworld.2game.info/jp_download.php?file_id={file_id}&id={mod_id}"
            
            # 一時ディレクトリ準備
            os.makedirs(TMP_DIR, exist_ok=True)
            os.makedirs(OLD_DIR, exist_ok=True)
            
            # ZIPファイルダウンロード
            zip_path = os.path.join(TMP_DIR, f"{file_id}_download.zip")
            download_zip(download_url, file_id, zip_path, self.pman)
            
            # アーカイブファイル検証
            if not is_archive_file(zip_path):
                self.logger.error(f"ダウンロードファイルがアーカイブ形式ではありません: {file_id}")
                return False
                
            # アーカイブ展開
            unpack_dir = os.path.join(TMP_DIR, f"{file_id}_unpack")
            if os.path.exists(unpack_dir):
                shutil.rmtree(unpack_dir, onerror=force_remove)
            extract_archive(zip_path, unpack_dir, self.pman)
            
            # Japaneseフォルダ検索
            jp_dir = find_japanese_dir(unpack_dir)
            if not jp_dir:
                self.logger.error(f"Japaneseフォルダが見つかりません: {file_id}")
                return False
                
            # 既存のJapaneseフォルダをバックアップ
            mod_path = mod_info['path']
            dest_jp_dir = os.path.join(mod_path, LANG_DIR_NAME, JP_DIR_NAME)
            
            if os.path.exists(dest_jp_dir):
                backup_dir = os.path.join(OLD_DIR, f"{mod_id}_old_japanese")
                if os.path.exists(backup_dir):
                    shutil.rmtree(backup_dir, onerror=force_remove)
                shutil.move(dest_jp_dir, backup_dir)
                self.logger.info(f"既存のJapaneseフォルダをバックアップ: {backup_dir}")
                
            # 新しいJapaneseフォルダをコピー
            shutil.copytree(jp_dir, dest_jp_dir)
            self.logger.info(f"Japaneseフォルダをコピー完了: {dest_jp_dir}")
            
            # ステータス更新
            status = self.load_japanization_status()
            status[mod_id] = {
                'applied_file_id': file_id,
                'applied_date': datetime.now().isoformat(),
                'mod_name': mod_name,
                'mod_type': mod_info['type']
            }
            self.save_japanization_status(status)
            
            # クリーンアップ
            shutil.move(zip_path, os.path.join(OLD_DIR, os.path.basename(zip_path)))
            shutil.rmtree(unpack_dir, onerror=force_remove)
            
            self.logger.info(f"日本語化適用完了: {mod_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"日本語化適用中にエラー: {e}")
            return False
            
    def run_auto_japanization(self):
        """一括日本語化処理を実行"""
        try:
            self.logger.info("=== 一括日本語化処理開始 ===")
            self.pman.set_status("一括日本語化処理開始...")
            
            # 翻訳リスト読み込み
            self.pman.set_status("翻訳リスト読み込み中...")
            translations = self.load_translation_list()
            if not translations:
                self.pman.popup_error("翻訳リストが見つからないか、読み込みに失敗しました。\n先にmod_list_getter.pyを実行してください。")
                return
                
            # インストール済みMOD取得
            self.pman.set_status("インストール済みMOD検索中...")
            installed_mods = self.get_installed_mods()
            if not installed_mods:
                self.pman.popup_warning("インストール済みのMODが見つかりませんでした。")
                return
                
            # 適用可能な翻訳検索
            self.pman.set_status("適用可能な翻訳検索中...")
            applicable = self.find_applicable_translations(installed_mods, translations)
            
            if not applicable:
                self.pman.popup_info("適用可能な新しい翻訳はありませんでした。")
                return
                
            # 一括適用実行
            self.pman.set_status(f"日本語化適用中... ({len(applicable)}件)")
            success_count = 0
            failed_count = 0
            
            for i, translation_info in enumerate(applicable):
                mod_name = translation_info['mod_info']['display_name']
                self.pman.set_progress(f"({i+1}/{len(applicable)}) {mod_name} 適用中...")
                
                if self.apply_japanization(translation_info):
                    success_count += 1
                else:
                    failed_count += 1
                    
            # 結果報告
            result_message = f"一括日本語化処理完了！\n\n成功: {success_count}件\n失敗: {failed_count}件"
            self.logger.info(f"処理結果: 成功 {success_count}件, 失敗 {failed_count}件")
            
            if failed_count > 0:
                result_message += f"\n\n失敗したMODの詳細はログファイルを確認してください。"
                
            self.pman.set_status("一括日本語化処理完了！")
            self.pman.popup_info(result_message)
            
        except Exception as e:
            self.logger.exception(f"一括日本語化処理中に予期しないエラー: {e}")
            self.pman.set_status("一括日本語化処理失敗")
            self.pman.popup_error(f"一括日本語化処理中にエラーが発生しました。\n{e}")
        finally:
            self.logger.info("=== 一括日本語化処理終了 ===")
            logging.shutdown()


def run_auto_japanization(pman):
    """一括日本語化処理のエントリーポイント"""
    auto_jp = AutoJapanizer(pman)
    auto_jp.run_auto_japanization()


