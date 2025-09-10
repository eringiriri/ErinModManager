import os
import re
import stat
import xml.etree.ElementTree as ET

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