import threading
import time
import os
import shutil
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

from config import *
from utils import extract_mod_id, fix_url, force_remove, find_japanese_dir
from downloader import download_zip, is_zip_file, extract_zip
from pages import open_mod_pages, open_steam_workshop
from mods_backup import backup_mods
from progress_utils import ProgressManager


class JapanizerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(WINDOW_TITLE)
        self.geometry(WINDOW_SIZE)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # UI操作を管理するマネージャー
        self.pman = ProgressManager(self)

        self._create_widgets()
        self._set_bindings()
        self.worker_thread = None

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

        # 実行ボタン
        self.install_button = ttk.Button(url_frame, text="実行", command=self._start_install)
        self.install_button.pack(side="left")

        # ステータス表示ラベル
        self.status_label = ttk.Label(self, text="準備完了", foreground=LABEL_STATUS_COLOR)
        self.status_label.pack(fill="x", padx=10, pady=5)
        
        # --- メイン操作ボタン ---
        actions_frame = ttk.Frame(self)
        actions_frame.pack(fill='x', padx=10, pady=5)

        # バックアップボタン
        self.backup_button = ttk.Button(actions_frame, text="全てのMODをバックアップ", command=self._backup_mods)
        self.backup_button.pack(fill="x", pady=(0, 5))

        # 一括日本語化ボタン (新規追加)
        self.apply_all_jp_button = ttk.Button(actions_frame, text="一括日本語ファイル適用", command=self._apply_all_jp_files)
        self.apply_all_jp_button.pack(fill="x")

        # --- フォルダを開くボタンエリア ---
        folder_frame = ttk.LabelFrame(self, text="フォルダを開く")
        folder_frame.pack(fill="x", padx=10, pady=(10, 5))

        folder_buttons_subframe = ttk.Frame(folder_frame)
        folder_buttons_subframe.pack(fill="x", padx=5, pady=5)

        self.workshop_mods_button = ttk.Button(folder_buttons_subframe, text="ワークショップMOD",
                                               command=self._open_workshop_mods_dir)
        self.workshop_mods_button.pack(side="left", fill="x", expand=True, padx=(0, 2))

        self.local_mods_button = ttk.Button(folder_buttons_subframe, text="ローカルMOD",
                                            command=self._open_local_mods_dir)
        self.local_mods_button.pack(side="left", fill="x", expand=True, padx=2)

        self.backup_folder_button = ttk.Button(folder_buttons_subframe, text="バックアップ",
                                               command=self._open_backup_dir)
        self.backup_folder_button.pack(side="left", fill="x", expand=True, padx=(2, 0))

    def _set_bindings(self):
        self.url_entry.bind("<Return>", self._start_install)

    def _start_worker_thread(self, target, args):
        """処理が重複しないようにワーカークラスを起動する"""
        if self.worker_thread and self.worker_thread.is_alive():
            self.pman.popup_warning("現在、別の処理が実行中です。")
            return
        self.worker_thread = threading.Thread(target=target, args=args, daemon=True)
        self.worker_thread.start()

    def _start_install(self, event=None):
        url = self.url_entry.get().strip()
        self._start_worker_thread(target=self._install_japanized, args=(url,))

    def _backup_mods(self):
        self._start_worker_thread(target=backup_mods, args=(self.pman,))
        
    def _apply_all_jp_files(self):
        """(未実装) 一括日本語化処理を呼び出す"""
        self.pman.popup_info("この機能はまだ実装されていません。")

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
        self.destroy()

    # --- フォルダを開く処理 ---
    def _open_folder(self, path, folder_name):
        """指定されたパスのフォルダを開き、存在しない場合は作成する"""
        try:
            if not os.path.isdir(path):
                # フォルダが存在しない場合、作成を試みる
                os.makedirs(path, exist_ok=True)
                self.pman.popup_info(f"{folder_name} が見つからなかったため、作成しました。\nパス: {path}")

            # フォルダを開く
            os.startfile(path)
        except Exception as e:
            self.pman.popup_error(f"{folder_name} を開けませんでした。\nパス: {path}\nエラー: {e}")

    def _open_workshop_mods_dir(self):
        self._open_folder(MODS_DIR, "ワークショップMODフォルダ")

    def _open_local_mods_dir(self):
        self._open_folder(LOCAL_MODS_DIR, "ローカルMODフォルダ")

    def _open_backup_dir(self):
        self._open_folder(BACKUP_ROOT, "バックアップフォルダ")

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

            # --- ZIP展開 ---
            if not is_zip_file(zip_path):
                open_mod_pages(mod_id)
                self.pman.popup_error("ダウンロードファイルがZIP形式ではありません。\nMOD配布ページを開きます。")
                return

            unpack_dir = os.path.join(TMP_DIR, UNPACK_DIR_FMT.format(mod_id))
            if os.path.exists(unpack_dir):
                shutil.rmtree(unpack_dir, onerror=force_remove)
            extract_zip(zip_path, unpack_dir, self.pman)

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