import threading
import time
import os
import shutil
import csv
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import webbrowser

from config import *
from gui_texts import *
from utils import extract_mod_id, fix_url, force_remove, find_japanese_dir, load_website_icon, open_folder
from downloader import download_zip, is_archive_file, extract_archive
from pages import open_mod_pages, open_steam_workshop, open_rimworld_2game
from logger import get_logger
from backup_manager import backup_mods
# ProgressManagerクラスを統合
class ProgressManager:
    """GUIのUI更新を管理し、別スレッドから安全に呼び出すためのクラス"""
    def __init__(self, gui):
        self.gui = gui

    def set_status(self, text):
        self.gui.set_status(text)
        
    def set_progress(self, text):
        self.gui.set_status(text)

    def popup_info(self, message):
        self.gui.popup_info(message)

    def popup_error(self, message):
        self.gui.popup_error(message)

    def popup_warning(self, message):
        self.gui.popup_warning(message)

    def popup_retry_cancel(self, message):
        return self.gui.popup_retry_cancel(message)
from auto_japanizer import run_auto_japanization
from translation_checker import check_translation_updates


class JapanizerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(WINDOW_TITLE)
        self.geometry(WINDOW_SIZE)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # ログ設定
        self.logger = get_logger("RimWorldJapanizer")
        self.logger.info(APP_STARTUP_LOG)

        # UI操作を管理するマネージャー
        self.pman = ProgressManager(self)

        self._create_widgets()
        self._set_bindings()
        self.worker_thread = None
        self._update_button_styles()  # 初期状態でボタンスタイルを更新
        
        # 起動時にステルスで更新チェック
        self.after(1000, self._startup_update_check)  # 1秒後に実行


    def _create_widgets(self):
        """GUIのウィジェットを配置する"""

        # 説明ラベル
        ttk.Label(self, text=LABEL_DESCRIPTION).pack(fill="x", padx=10, pady=(10, 5))

        # --- URL入力 & 実行ボタン ---
        url_frame = ttk.Frame(self)
        url_frame.pack(fill='x', padx=10, pady=(0, 5))

        # URL入力欄
        self.url_entry = ttk.Entry(url_frame)
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=2, padx=(0, 5))
        self.url_entry.focus_set()

        # ウェブサイトボタン（実行ボタンの上）
        self.website_button = tk.Button(url_frame, 
                                        command=self._open_website, 
                                        relief="flat", 
                                        bd=0,
                                        highlightthickness=0)
        self.website_button.pack(side="left", padx=(0, 5))
        
        # アイコンを読み込み
        load_website_icon(self.website_button)

        # 実行ボタン
        self.install_button = ttk.Button(url_frame, text=EXECUTE_BUTTON_TEXT, command=self._start_install)
        self.install_button.pack(side="left")

        # ステータス表示ラベル
        self.status_label = ttk.Label(self, text=READY_STATUS, foreground=LABEL_STATUS_COLOR)
        self.status_label.pack(fill="x", padx=10, pady=5)
        
        # --- メイン操作ボタン ---
        actions_frame = ttk.LabelFrame(self, text=MAIN_OPERATIONS_FRAME_TITLE)
        actions_frame.pack(fill='x', padx=10, pady=5)

        # ボタンを3列に配置
        button_frame = ttk.Frame(actions_frame)
        button_frame.pack(fill='x', padx=5, pady=5)

        # 左列
        left_frame = ttk.Frame(button_frame)
        left_frame.pack(side="left", fill="x", expand=True, padx=(0, 2))

        # 中央列
        center_frame = ttk.Frame(button_frame)
        center_frame.pack(side="left", fill="x", expand=True, padx=2)

        # 右列
        right_frame = ttk.Frame(button_frame)
        right_frame.pack(side="right", fill="x", expand=True, padx=(2, 0))

        # 左列：バックアップボタン
        self.backup_button = ttk.Button(left_frame, text=BACKUP_BUTTON_TEXT, command=self._backup_mods)
        self.backup_button.pack(fill="x")

        # 中央列：翻訳関連ボタン
        self.update_csv_button = ttk.Button(center_frame, text=UPDATE_CHECK_BUTTON_TEXT, command=self._update_translation_list)
        self.update_csv_button.pack(fill="x", pady=(0, 5))

        self.full_scrape_button = ttk.Button(center_frame, text=FULL_SCRAPE_BUTTON_TEXT, command=self._full_scrape_translation_list)
        self.full_scrape_button.pack(fill="x")

        # 右列：適用・削除ボタン
        self.apply_all_jp_button = ttk.Button(right_frame, text=APPLY_ALL_JP_BUTTON_TEXT, command=self._apply_all_jp_files)
        self.apply_all_jp_button.pack(fill="x", pady=(0, 5))

        self.delete_csv_button = ttk.Button(right_frame, text=DELETE_CSV_BUTTON_TEXT, command=self._delete_csv)
        self.delete_csv_button.pack(fill="x")

        # --- フォルダを開くボタンエリア ---
        folder_frame = ttk.LabelFrame(self, text=FOLDER_FRAME_TITLE)
        folder_frame.pack(fill="x", padx=10, pady=(10, 5))

        # 1行目：フォルダ関連ボタン
        folder_buttons_subframe1 = ttk.Frame(folder_frame)
        folder_buttons_subframe1.pack(fill="x", padx=5, pady=(5, 2))

        self.workshop_mods_button = ttk.Button(folder_buttons_subframe1, text=WORKSHOP_MODS_BUTTON_TEXT,
                                               command=self._open_workshop_mods_dir)
        self.workshop_mods_button.pack(side="left", fill="x", expand=True, padx=(0, 2))

        self.local_mods_button = ttk.Button(folder_buttons_subframe1, text=LOCAL_MODS_BUTTON_TEXT,
                                            command=self._open_local_mods_dir)
        self.local_mods_button.pack(side="left", fill="x", expand=True, padx=2)

        self.backup_folder_button = ttk.Button(folder_buttons_subframe1, text="バックアップ",
                                               command=self._open_backup_dir)
        self.backup_folder_button.pack(side="left", fill="x", expand=True, padx=(2, 0))



    def _startup_update_check(self):
        """起動時のステルス更新チェック"""
        try:
            self.logger.info("起動時更新チェック開始")
            # CSVファイルが存在する場合のみチェック
            csv_path = os.path.join(LOGS_DIR, CSV_FILENAME)
            if not os.path.exists(csv_path):
                self.logger.info("CSVファイルが存在しないため起動時チェックをスキップ")
                return
                
            # バックグラウンドで更新チェックを実行
            threading.Thread(target=self._check_updates_silently, daemon=True).start()
            
        except Exception as e:
            self.logger.error(f"起動時更新チェック中にエラー: {e}")

    def _check_updates_silently(self):
        """バックグラウンドで更新をチェック"""
        try:
            self.logger.info("バックグラウンド更新チェック開始")
            # ステータス表示
            self.pman.set_status("起動時更新チェック中...")
            
            from translation_checker import TranslationChecker
            checker = TranslationChecker(self.pman)
            
            # 最新投稿をチェック
            new_translations = checker._get_latest_translations()
            if not new_translations:
                self.logger.info("新しい翻訳ファイルは見つかりませんでした")
                self.pman.set_status("準備完了")
                return
                
            # 既存のCSVファイルからFile IDを取得
            csv_path = os.path.join(LOGS_DIR, CSV_FILENAME)
            existing_file_ids = set()
            
            with open(csv_path, 'r', encoding=CSV_ENCODING) as f:
                reader = csv.DictReader(f)
                existing_file_ids = {row['File ID'] for row in reader}
            
            # 新しいFile IDを検出
            new_file_ids = {t['File ID'] for t in new_translations}
            added_file_ids = new_file_ids - existing_file_ids
            
            if added_file_ids:
                self.logger.info(f"新しい翻訳ファイルを {len(added_file_ids)} 件発見")
                # メインスレッドで確認ダイアログを表示
                self.after(0, lambda: self._ask_update_csv(len(added_file_ids)))
            else:
                self.logger.info("新しい翻訳ファイルは見つかりませんでした")
                self.pman.set_status("準備完了")
                
        except Exception as e:
            self.logger.error(f"バックグラウンド更新チェック中にエラー: {e}")
            # エラー時もステータスを戻す
            self.pman.set_status("準備完了")

    def _ask_update_csv(self, new_count):
        """CSV更新の確認を求める"""
        self.logger.info(f"CSV更新確認ダイアログ表示: {new_count}件の新しい翻訳ファイル")
        if messagebox.askyesno("翻訳更新検出", 
                              f"新しい翻訳ファイルが {new_count} 件見つかりました。\n\n"
                              f"翻訳リストを更新しますか？\n\n"
                              f"※「いいえ」を選択しても、後から「更新チェック」ボタンで更新できます。"):
            # 更新を実行
            self.logger.info("ユーザーがCSV更新を選択")
            self._start_worker_thread(target=self._update_csv_worker, args=())
        else:
            # キャンセルした場合はステータスを戻す
            self.logger.info("ユーザーがCSV更新をキャンセル")
            self.pman.set_status("準備完了")

    def _set_bindings(self):
        self.url_entry.bind("<Return>", self._start_install)

    def _start_worker_thread(self, target, args):
        """処理が重複しないようにワーカークラスを起動する"""
        if self.worker_thread and self.worker_thread.is_alive():
            self.pman.popup_warning("現在、別の処理が実行中です。")
            return
        self.worker_thread = threading.Thread(target=target, args=args, daemon=True)
        self.worker_thread.start()
        self._set_buttons_running_state(True)

    def _start_install(self, event=None):
        url = self.url_entry.get().strip()
        self.logger.info(f"個別インストール開始: URL={url}")
        self._start_worker_thread(target=self._install_worker, args=(url,))
        
    def _install_worker(self, url):
        """個別インストールのワーカー関数"""
        try:
            self.logger.info(f"個別インストール処理開始: URL={url}")
            self._install_japanized(url)
            self.logger.info("個別インストール処理完了")
        except Exception as e:
            self.logger.error(f"個別インストール処理中にエラー: {e}")
        finally:
            self._set_buttons_running_state(False)  # 処理完了後にボタン状態を戻す
            self.pman.set_status("準備完了")  # ステータスを準備完了に戻す
            # CSVの状態を再確認してボタンスタイルを更新
            self._update_button_styles()

    def _backup_mods(self):
        self.logger.info("MODバックアップ開始")
        self._start_worker_thread(target=self._backup_worker, args=())
        
    def _backup_worker(self):
        """バックアップのワーカー関数"""
        try:
            self.logger.info("MODバックアップ処理開始")
            backup_mods(self.pman)
            self.logger.info("MODバックアップ処理完了")
        except Exception as e:
            self.logger.error(f"MODバックアップ処理中にエラー: {e}")
        finally:
            self._set_buttons_running_state(False)  # 処理完了後にボタン状態を戻す
            self.pman.set_status("準備完了")  # ステータスを準備完了に戻す
            # CSVの状態を再確認してボタンスタイルを更新
            self._update_button_styles()
        
    def _apply_all_jp_files(self):
        """一括日本語化処理を呼び出す"""
        self.logger.info("一括日本語化開始")
        self._start_worker_thread(target=self._apply_all_jp_worker, args=())
        
    def _apply_all_jp_worker(self):
        """一括日本語化のワーカー関数"""
        try:
            self.logger.info("一括日本語化処理開始")
            run_auto_japanization(self.pman)
            self.logger.info("一括日本語化処理完了")
        except Exception as e:
            self.logger.error(f"一括日本語化処理中にエラー: {e}")
        finally:
            self._set_buttons_running_state(False)  # 処理完了後にボタン状態を戻す
            self.pman.set_status("準備完了")  # ステータスを準備完了に戻す
            # CSVの状態を再確認してボタンスタイルを更新
            self._update_button_styles()
        
    def _update_translation_list(self):
        """翻訳リストを更新する（CSVがあるときのみ）"""
        csv_path = os.path.join(LOGS_DIR, CSV_FILENAME)
        if not os.path.exists(csv_path):
            self.logger.warning("CSVファイルが存在しないため更新チェックをスキップ")
            self.pman.popup_warning("CSVファイルが存在しません。\n「全ページ取得」ボタンで新規作成してください。")
            return
        self.logger.info("翻訳リスト更新開始")
        self._start_worker_thread(target=self._update_csv_worker, args=())
        
    def _full_scrape_translation_list(self):
        """全ページを取得して翻訳リストを作成する"""
        self.logger.info("全ページ取得開始")
        self._start_worker_thread(target=self._full_scrape_worker, args=())
        
    def _update_csv_worker(self):
        """CSV更新のワーカー関数"""
        try:
            self.logger.info("CSV更新処理開始")
            check_translation_updates(self.pman)
            self.logger.info("CSV更新処理完了")
        except Exception as e:
            self.logger.error(f"CSV更新処理中にエラー: {e}")
        finally:
            self._set_buttons_running_state(False)  # 処理完了後にボタン状態を戻す
            self.pman.set_status("準備完了")  # ステータスを準備完了に戻す
            # CSVの状態を再確認してボタンスタイルを更新
            self._update_button_styles()
            
    def _full_scrape_worker(self):
        """全ページ取得のワーカー関数"""
        try:
            self.logger.info("全ページ取得処理開始")
            from translation_scraper import scrape_and_save_to_csv
            scrape_and_save_to_csv(self.pman)
            self.logger.info("全ページ取得処理完了")
            self.pman.popup_info("全ページ取得が完了しました。\n「一括日本語ファイル適用」ボタンで適用できます。")
        except Exception as e:
            self.logger.error(f"全ページ取得処理中にエラー: {e}")
        finally:
            self._set_buttons_running_state(False)  # 処理完了後にボタン状態を戻す
            self.pman.set_status("準備完了")  # ステータスを準備完了に戻す
            # CSVの状態を再確認してボタンスタイルを更新
            self._update_button_styles()
            
    def _delete_csv(self):
        """CSVファイルを削除する"""
        csv_path = os.path.join(LOGS_DIR, CSV_FILENAME)
        
        if not os.path.exists(csv_path):
            self.pman.popup_info("CSVファイルは存在しません。")
            return
            
        # 確認ダイアログ
        if messagebox.askyesno("確認", "CSVファイルを削除しますか？\n\n削除後は「最新翻訳チェック」で新規作成できます。"):
            try:
                os.remove(csv_path)
                self.pman.popup_info("CSVファイルを削除しました。")
                # ボタン状態を強制的に更新（CSV削除後の状態）
                self._force_update_button_styles()
            except Exception as e:
                self.pman.popup_error(f"CSVファイルの削除に失敗しました。\n{e}")
                
    def _set_buttons_running_state(self, is_running):
        """処理実行中のボタン状態を制御"""
        if is_running:
            # 実行中：すべてのボタンを無効化
            self.install_button.config(state="disabled")
            self.backup_button.config(state="disabled")
            self.apply_all_jp_button.config(state="disabled")
            self.update_csv_button.config(state="disabled")
            self.full_scrape_button.config(state="disabled")
            self.delete_csv_button.config(state="disabled")
        else:
            # 待機中：通常の状態に戻す
            self.install_button.config(state="normal")
            self.backup_button.config(state="normal")
            # 翻訳関連ボタンを有効にする
            self.update_csv_button.config(state="normal")
            self.full_scrape_button.config(state="normal")
            self._update_button_styles()  # CSVの状態に応じて更新
            
    def _force_update_button_styles(self):
        """CSV削除後のボタンスタイルを強制更新"""
        # CSVが存在しない状態に強制設定
        self.update_csv_button.config(text="更新チェック", style="TButton")
        self.delete_csv_button.config(state="disabled")
        self.apply_all_jp_button.config(state="disabled")
        # 翻訳関連ボタンは常に有効
        self.update_csv_button.config(state="normal")
        self.full_scrape_button.config(state="normal")
        
    def _update_button_styles(self):
        """CSVファイルの存在に応じてボタンスタイルを更新"""
        csv_path = os.path.join(LOGS_DIR, CSV_FILENAME)
        csv_exists = os.path.exists(csv_path)
        
        if csv_exists:
            # CSVが存在する場合：通常のスタイル
            self.update_csv_button.config(text="更新チェック", style="TButton")
            self.delete_csv_button.config(state="normal")
            self.apply_all_jp_button.config(state="normal")
        else:
            # CSVが存在しない場合：目立つスタイル
            self.update_csv_button.config(text="更新チェック", style="TButton")
            self.delete_csv_button.config(state="disabled")
            self.apply_all_jp_button.config(state="disabled")
        
        # 翻訳関連ボタンは常に有効（中止後も含む）
        self.update_csv_button.config(state="normal")
        self.full_scrape_button.config(state="normal")

    # --- pmanから呼ばれるUI更新メソッド ---
    def set_status(self, text):
        self.after(0, lambda: self.status_label.config(text=text))

    def popup_info(self, message):
        self.after(0, lambda: messagebox.showinfo(WINDOW_TITLE, message))

    def popup_error(self, message):
        self.after(0, lambda: messagebox.showerror("エラー", message))

    def popup_warning(self, message):
        self.after(0, lambda: messagebox.showwarning("注意", message))

    def popup_retry_cancel(self, message):
        return messagebox.askretrycancel("確認", message)

    def on_close(self):
        self.logger.info("=== RimWorld Japanizer 終了 ===")
        self.destroy()

    # --- フォルダを開く処理 ---
    def _open_workshop_mods_dir(self):
        self.logger.info("ワークショップMODフォルダを開く")
        open_folder(MODS_DIR, "ワークショップMODフォルダ", self.pman)

    def _open_local_mods_dir(self):
        self.logger.info("ローカルMODフォルダを開く")
        open_folder(LOCAL_MODS_DIR, "ローカルMODフォルダ", self.pman)

    def _open_backup_dir(self):
        self.logger.info("バックアップフォルダを開く")
        open_folder(BACKUP_ROOT, "バックアップフォルダ", self.pman)

    def _open_website(self):
        """rimworld.2game.infoサイトを開く"""
        try:
            self.logger.info("rimworld.2game.infoサイトを開く")
            open_rimworld_2game()
        except Exception as e:
            self.logger.error(f"ウェブサイトを開けませんでした: {e}")
            self.pman.popup_error(f"ウェブサイトを開けませんでした。\n{e}")

    def _install_japanized(self, url):
        """日本語化MODのインストール処理"""
        try:
            self.pman.set_status("入力値確認中…")
            if not url:
                self.pman.popup_error("URLが空です。")
                return

            mod_id = extract_mod_id(url)
            if not mod_id:
                self.pman.popup_error("MOD IDがURLから取得できませんでした。")
                return

            # --- 処理の準備 ---
            fixed_url = fix_url(url, mod_id)
            self.pman.set_status(f"MOD ID: {mod_id} の準備中…")
            os.makedirs(TMP_DIR, exist_ok=True)
            os.makedirs(OLD_DIR, exist_ok=True)

            # --- ダウンロード ---
            zip_path = os.path.join(TMP_DIR, ZIP_FILENAME_FMT.format(mod_id))
            download_zip(fixed_url, mod_id, zip_path, self.pman)

            # --- アーカイブ展開 ---
            if not is_archive_file(zip_path):
                open_mod_pages(mod_id)
                self.pman.popup_error("ダウンロードファイルがアーカイブ形式ではありません。\nMOD配布ページを開きます。")
                return

            unpack_dir = os.path.join(TMP_DIR, UNPACK_DIR_FMT.format(mod_id))
            if os.path.exists(unpack_dir):
                shutil.rmtree(unpack_dir, onerror=force_remove)
            extract_archive(zip_path, unpack_dir, self.pman)

            # --- Japaneseフォルダの検出とコピー ---
            jp_dir = find_japanese_dir(unpack_dir)
            if not jp_dir:
                self.pman.popup_error("Japaneseフォルダが見つかりません。")
                return

            # --- MODフォルダの確認 ---
            mod_dir = os.path.join(MODS_DIR, mod_id)
            while not os.path.isdir(mod_dir):
                self.pman.set_status("MODフォルダ未検出。Steamページを開きます。")
                open_steam_workshop(mod_id)
                if not self.pman.popup_retry_cancel(
                        "MODが見つかりませんでした。\nサブスクライブ後、『再試行』を押してください。"):
                    self.pman.popup_info("処理をキャンセルしました。")
                    return
                time.sleep(1)  # Steamクライアントの処理待ち

            # --- コピー実行 ---
            self.pman.set_status("Japaneseフォルダをコピー中…")
            dest_jp_dir = os.path.join(mod_dir, LANG_DIR_NAME, JP_DIR_NAME)
            if os.path.exists(dest_jp_dir):
                shutil.rmtree(dest_jp_dir, onerror=force_remove)
            shutil.copytree(jp_dir, dest_jp_dir)

            # --- 後処理 ---
            self.pman.set_status("クリーンアップ中…")
            shutil.move(zip_path, os.path.join(OLD_DIR, os.path.basename(zip_path)))
            shutil.rmtree(unpack_dir, onerror=force_remove)

            self.pman.set_status(f"MOD ID: {mod_id} の日本語化完了！")
            self.after(0, lambda: self.url_entry.delete(0, tk.END))

        except Exception as ex:
            self.pman.popup_error(f"予期しないエラーが発生しました。\n{ex}")
            self.pman.set_status("エラーが発生しました。")


if __name__ == "__main__":
    app = JapanizerGUI()
    app.mainloop()