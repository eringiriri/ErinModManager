import os
import requests
import zipfile
import rarfile

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

def get_archive_type(file_path):
    """アーカイブファイルの形式を判定する"""
    if zipfile.is_zipfile(file_path):
        return "zip"
    try:
        if rarfile.is_rarfile(file_path):
            return "rar"
    except:
        pass
    return None

def is_archive_file(path):
    """ファイルがアーカイブ形式か判定する"""
    return get_archive_type(path) is not None

def extract_archive(archive_path, unpack_dir, pman):
    """アーカイブファイル（ZIP/RAR）を展開する"""
    archive_type = get_archive_type(archive_path)
    
    if archive_type == "zip":
        pman.set_status("ZIPアーカイブ展開中…")
        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(unpack_dir)
        except Exception as e:
            pman.popup_error(f"ZIPアーカイブ展開中にエラーが発生しました。\n{e}")
            pman.set_status("ZIP展開失敗。")
            raise
            
    elif archive_type == "rar":
        pman.set_status("RARアーカイブ展開中…")
        try:
            with rarfile.RarFile(archive_path, 'r') as rf:
                rf.extractall(unpack_dir)
        except Exception as e:
            pman.popup_error(f"RARアーカイブ展開中にエラーが発生しました。\n{e}")
            pman.set_status("RAR展開失敗。")
            raise
    else:
        raise ValueError(f"サポートされていないアーカイブ形式です: {archive_path}")
