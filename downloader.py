import os
import requests
import zipfile

from config import REFERER_FMT, USER_AGENT, CHUNK_SIZE, TIMEOUT

def download_zip(url, mod_id, zip_path, pman):
    """ファイルをダウンロードする"""
    pman.set_status("ファイルダウンロード中…")
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
            except OSError:
                pass
        pman.popup_error(f"ダウンロード中にエラーが発生しました。\n{e}")
        pman.set_status("ダウンロード失敗")
        raise

def is_zip_file(path):
    """ファイルがZIP形式か判定する"""
    return zipfile.is_zipfile(path)

def extract_zip(zip_path, unpack_dir, pman):
    """ZIPアーカイブを展開する"""
    pman.set_status("ZIPアーカイブ展開中…")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(unpack_dir)
    except Exception as e:
        pman.popup_error(f"アーカイブ展開中にエラーが発生しました。\n{e}")
        pman.set_status("ZIP展開失敗。")
        raise