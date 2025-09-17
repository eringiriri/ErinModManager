import os
import re
import stat
import io
import xml.etree.ElementTree as ET
import requests
from PIL import Image, ImageTk

from config import JP_DIR_NAME

def sanitize_filename(name):
    """ファイル名やディレクトリ名として使えない文字を置換する"""
    # Windowsで使えない文字: \ / : * ? " < > |
    # \ と / は os.path.join が通常扱いますが、安全のために含めます
    invalid_chars = r'[\\/:*?"<>|]'
    return re.sub(invalid_chars, '_', name)

def get_mod_name_from_xml(mod_path):
    """MODのAbout/About.xmlから<name>タグの内容を読み取る"""
    about_xml_path = os.path.join(mod_path, "About", "About.xml")
    try:
        if os.path.exists(about_xml_path):
            tree = ET.parse(about_xml_path)
            root = tree.getroot()
            name_tag = root.find('name')
            if name_tag is not None and name_tag.text:
                return name_tag.text.strip()
    except (ET.ParseError, FileNotFoundError):
        # XMLの解析エラーやファイルが見つからない場合はNoneを返す
        pass
    return None

def extract_mod_id(url):
    """URLからMODのIDを抽出する（Steamとrimworld.2game.infoの両対応）"""
    m = re.search(r'id=(\d+)', url)
    if m:
        return m.group(1)
    return None

def fix_url(url, mod_id):
    """rimworld.2game.info用のURL形式を修正する"""
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = "https://rimworld.2game.info" + url
    return url

def force_remove(func, path, exc_info):
    """読み取り専用ファイルを削除するためのエラーハンドラ"""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def find_japanese_dir(root):
    """指定されたフォルダ内で'Japanese'または'Japanese (日本語)'という名前のフォルダを探す"""
    japanese_variants = [
        JP_DIR_NAME,  # "Japanese"
        "Japanese (日本語)",
        "Japanese(日本語)",
        "Japanese_日本語",
        "Japanese-日本語"
    ]
    
    for dirpath, dirnames, _ in os.walk(root):
        for dirname in dirnames:
            # 完全一致チェック
            if dirname in japanese_variants:
                return os.path.join(dirpath, dirname)
            # 大文字小文字を無視したチェック
            if any(variant.lower() == dirname.lower() for variant in japanese_variants):
                return os.path.join(dirpath, dirname)
            # "Japanese"で始まるフォルダもチェック
            if dirname.lower().startswith("japanese"):
                return os.path.join(dirpath, dirname)
    return None

def open_folder(path, folder_name, pman=None):
    """指定されたパスのフォルダを開き、存在しない場合は作成する"""
    try:
        if not os.path.isdir(path):
            # フォルダが存在しない場合、作成を試みる
            os.makedirs(path, exist_ok=True)
            if pman:
                pman.popup_info(f"{folder_name} が見つからなかったため、作成しました。\nパス: {path}")

        # フォルダを開く
        os.startfile(path)
    except Exception as e:
        if pman:
            pman.popup_error(f"{folder_name} を開けませんでした。\nパス: {path}\nエラー: {e}")
        raise

def load_website_icon(button, icon_url="https://rimworld.2game.info/images/icon48x48.png"):
    """ウェブサイトのアイコンを読み込んでボタンに設定する"""
    try:
        # アイコンをダウンロード
        response = requests.get(icon_url, timeout=10)
        response.raise_for_status()
        
        # PILで画像を読み込み
        icon_image = Image.open(io.BytesIO(response.content))
        
        # 32x32にリサイズ（ボタンに適したサイズ）
        icon_image = icon_image.resize((32, 32), Image.Resampling.LANCZOS)
        
        # Tkinter用のPhotoImageに変換
        website_icon = ImageTk.PhotoImage(icon_image)
        
        # ボタンにアイコンを設定（アイコン自体がボタンになる）
        button.config(image=website_icon)
        
        # 参照を保持（ガベージコレクション防止）
        button.image = website_icon
        
    except Exception as e:
        # アイコンの読み込みに失敗した場合はエモジで表示
        button.config(text="🌐", font=("Arial", 16))