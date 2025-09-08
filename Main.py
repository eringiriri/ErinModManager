import os
import re
import shutil
import threading
import tkinter as tk
from tkinter import messagebox
import zipfile
import requests
import webbrowser
import time

# ----------- ハードコード設定 -----------

# --- ディレクトリパス ---
MODS_DIR = r"S:\SteamLibrary\steamapps\workshop\content\294100"
JAPANIZED_DIR = os.path.join(os.path.dirname(MODS_DIR), "japanized")
TMP_DIR = os.path.join(JAPANIZED_DIR, "TMP")
OLD_DIR = os.path.join(JAPANIZED_DIR, "old")

# --- フォルダ・ファイル関連 ---
LANG_DIR_NAME = "Languages"
JP_DIR_NAME = "Japanese"
ZIP_FILENAME_FMT = "{}_download.zip"
UNPACK_DIR_FMT = "{}_unpack"

# --- GUI表示・スタイル ---
WINDOW_TITLE = "RimWorld MOD 日本語化インストーラー"
WINDOW_SIZE = "480x120"
LABEL_DESCRIPTION = "日本語化パックのURLを入力し、Enterを押してください。"
ENTRY_WIDTH = 70
LABEL_STATUS_COLOR = "#007000"

# --- URL・API関連 ---
STEAM_URL_FMT = "https://steamcommunity.com/sharedfiles/filedetails/?id={}"
RIM2GAME_URL_FMT = "https://rimworld.2game.info/detail.php?id={}"

# --- HTTPダウンロード ---
REFERER_FMT = "https://rimworld.2game.info/detail.php?id={}"
USER_AGENT = "RimWorldJapanizer/1.0 (+https://rimworld.2game.info)"
CHUNK_SIZE = 1024 * 100
TIMEOUT = 30

# ----------- メインクラス -----------
class JapanizerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(WINDOW_TITLE)
        self.geometry(WINDOW_SIZE)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._create_widgets()
        self._set_bindings()
        self.download_thread = None

    def _create_widgets(self):
        self.desc_label = tk.Label(self, text=LABEL_DESCRIPTION)
        self.desc_label.pack(pady=(16, 2))
        self.url_entry = tk.Entry(self, width=ENTRY_WIDTH)
        self.url_entry.pack(pady=(0, 2))
        self.url_entry.focus_set()
        self.status_label = tk.Label(self, text="", anchor="w", fg=LABEL_STATUS_COLOR)
        self.status_label.pack(pady=(2, 0), fill="x")

    def _set_bindings(self):
        self.url_entry.bind("<Return>", self._start_install)

    def _start_install(self, event=None):
        url = self.url_entry.get().strip()
        if self.download_thread and self.download_thread.is_alive():
            return
        self.download_thread = threading.Thread(target=self._install_japanized, args=(url,))
        self.download_thread.daemon = True
        self.download_thread.start()

    def set_status(self, text):
        def update():
            self.status_label.config(text=text)
        self.after(0, update)

    def popup_info(self, message):
        self.after(0, lambda: messagebox.showinfo("日本語化インストーラー", message))

    def popup_error(self, message):
        self.after(0, lambda: messagebox.showerror("エラー", message))

    def popup_warning(self, message):
        self.after(0, lambda: messagebox.showwarning("注意", message))

    def popup_retry_cancel(self, message):
        return messagebox.askretrycancel("サブスクライブ確認", message)

    def on_close(self):
        self.destroy()

    def _install_japanized(self, url):
        try:
            self.set_status("入力値確認中…")
            if not url:
                self.popup_error("URLが空です。日本語化パックのURLを入力してください。")
                self.set_status("URLが空です。")
                return
            mod_id = self._extract_mod_id(url)
            if not mod_id:
                self.popup_error("MOD IDがURLから取得できませんでした。URL形式を確認してください。")
                self.set_status("MOD ID抽出失敗。")
                return

            url = self._fix_url(url, mod_id)
            self.set_status(f"MOD ID: {mod_id}  ダウンロード準備中…")
            self._prepare_dirs()
            zip_path = os.path.join(TMP_DIR, ZIP_FILENAME_FMT.format(mod_id))
            self._download_zip(url, mod_id, zip_path)

            self.set_status("ダウンロードファイル確認中…")
            if not zipfile.is_zipfile(zip_path):
                try:
                    os.remove(zip_path)
                except Exception:
                    pass
                self._open_mod_pages(mod_id)
                self.popup_error("ダウンロードファイルがZIP形式ではありません。\nMOD配布元ページを自動で開きますので手動でご確認ください。")
                self.set_status("ZIPでないため中断。")
                return

            unpack_dir = os.path.join(TMP_DIR, UNPACK_DIR_FMT.format(mod_id))
            if os.path.exists(unpack_dir):
                shutil.rmtree(unpack_dir, onerror=self._force_remove)
            os.makedirs(unpack_dir, exist_ok=True)
            self.set_status("ZIPアーカイブ展開中…")
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(unpack_dir)
            except Exception as e:
                self.popup_error(f"アーカイブ展開中にエラーが発生しました。\n{e}")
                self.set_status("ZIP展開失敗。")
                return

            self.set_status("Japaneseフォルダ検出中…")
            jp_dir = self._find_japanese_dir(unpack_dir)
            if not jp_dir:
                self.popup_error("Japaneseフォルダが見つかりません。\n対応外の構造か破損アーカイブの可能性。")
                self.set_status("Japanese未検出。")
                return

            mod_dir = os.path.join(MODS_DIR, mod_id)
            while not os.path.isdir(mod_dir):
                self.set_status("MODフォルダ未検出。Steamページを開きます。")
                self._open_steam_workshop(mod_id)
                retry = self.popup_retry_cancel(
                    "MODが見つかりませんでした。\nサブスクライブ後、『再試行』を押してください。\nキャンセルで処理を停止します。"
                )
                if not retry:
                    self.popup_info("キャンセルされました。未サブスクライブか、RimWorld未起動、\n番号ミスの可能性があります。")
                    self.set_status("MODフォルダ未発見、中止。")
                    return
                self.set_status("MODフォルダ再チェック中…")
                time.sleep(1)

            self.set_status("Japaneseフォルダコピー中…")
            lang_dir = os.path.join(mod_dir, LANG_DIR_NAME)
            dest_jp_dir = os.path.join(lang_dir, JP_DIR_NAME)

            if os.path.exists(dest_jp_dir):
                try:
                    shutil.rmtree(dest_jp_dir, onerror=self._force_remove)
                except Exception as e:
                    self.popup_error(f"Japaneseディレクトリ削除失敗\n{e}")
                    self.set_status("既存Japanese削除失敗。")
                    return
            os.makedirs(lang_dir, exist_ok=True)
            try:
                shutil.copytree(jp_dir, dest_jp_dir)
            except Exception as e:
                self.popup_error(f"Japaneseフォルダのコピーに失敗しました。\n{e}")
                self.set_status("コピー失敗。")
                return

            self.set_status("クリーンナップ中…")
            os.makedirs(OLD_DIR, exist_ok=True)
            shutil.move(zip_path, os.path.join(OLD_DIR, os.path.basename(zip_path)))
            if os.path.exists(unpack_dir):
                shutil.rmtree(unpack_dir, onerror=self._force_remove)

            self.set_status("完了！")
            self.after(0, lambda: self.url_entry.delete(0, tk.END))
        except Exception as ex:
            self.popup_error(f"予期しないエラーが発生しました。\n{ex}")
            self.set_status("不明なエラー。")

    def _extract_mod_id(self, url):
        m = re.search(r'&id=(\d+)', url)
        if m:
            return m.group(1)
        return None

    def _fix_url(self, url, mod_id):
        url = url.strip()
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = "https://rimworld.2game.info" + url
        return url

    def _prepare_dirs(self):
        os.makedirs(JAPANIZED_DIR, exist_ok=True)
        os.makedirs(TMP_DIR, exist_ok=True)
        os.makedirs(OLD_DIR, exist_ok=True)

    def _download_zip(self, url, mod_id, zip_path):
        self.set_status("ファイルダウンロード中…")
        headers = {
            "Referer": REFERER_FMT.format(mod_id),
            "User-Agent": USER_AGENT
        }
        try:
            with requests.get(url, headers=headers, stream=True, timeout=TIMEOUT) as r:
                r.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
        except Exception as e:
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except Exception:
                    pass
            self.popup_error(f"ダウンロード中にエラーが発生しました。\n{e}")
            self.set_status("ダウンロード失敗")
            raise

    def _find_japanese_dir(self, root):
        # "Japanese" を含むフォルダを許可
        for dirpath, dirnames, filenames in os.walk(root):
            for dirname in dirnames:
                if JP_DIR_NAME.lower() in dirname.lower():
                    return os.path.join(dirpath, dirname)
        return None

    def _open_mod_pages(self, mod_id):
        steam_url = STEAM_URL_FMT.format(mod_id)
        rim2game_url = RIM2GAME_URL_FMT.format(mod_id)
        webbrowser.open(steam_url)
        webbrowser.open(rim2game_url)

    def _open_steam_workshop(self, mod_id):
        steam_url = STEAM_URL_FMT.format(mod_id)
        webbrowser.open(steam_url)

    def _force_remove(self, func, path, exc):
        import stat
        os.chmod(path, stat.S_IWRITE)
        func(path)

if __name__ == "__main__":
    app = JapanizerGUI()
    app.mainloop()