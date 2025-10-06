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

def parse_load_folders(load_folders_path):
    """
    LoadFolders.xmlを解析して、バージョンごとのフォルダ指定を取得
    戻り値: {version: [folder_list]} の辞書
    """
    import xml.etree.ElementTree as ET
    
    try:
        tree = ET.parse(load_folders_path)
        root = tree.getroot()
        
        result = {}
        for version_elem in root:
            version = version_elem.tag  # v1.6, v1.5, etc.
            folders = []
            for li in version_elem:
                if li.text:
                    folders.append(li.text.strip())
            result[version] = folders
        
        return result
    except Exception as e:
        # XML解析エラーの場合は空の辞書を返す
        return {}

def get_current_rimworld_version():
    """
    現在のRimWorldバージョンを取得
    将来的にはAbout.xmlから自動取得するか、設定ファイルから読み取る
    """
    # 現在は1.6をデフォルトとする
    return "1.6"

def determine_placement_locations(mod_path):
    """
    MODフォルダ内の適切な配置場所を決定する（複数バージョン対応）
    戻り値: [配置場所のリスト]
    """
    placement_locations = []
    
    # 1. ルートレベルのLanguagesフォルダ確認
    root_languages = os.path.join(mod_path, "Languages")
    if os.path.exists(root_languages):
        placement_locations.append(root_languages)
        return placement_locations  # ルートにLanguagesがある場合は、それのみを使用
    
    # 2. LoadFolders.xmlの存在と内容確認
    load_folders_path = os.path.join(mod_path, "LoadFolders.xml")
    if os.path.exists(load_folders_path):
        load_folders_content = parse_load_folders(load_folders_path)
        current_version = get_current_rimworld_version()
        
        # 現在のバージョンに対応するフォルダを確認
        version_key = f"v{current_version}"
        if version_key in load_folders_content:
            folders = load_folders_content[version_key]
            
            # ルートディレクトリ（"/"）が指定されているかチェック
            if "/" in folders:
                # ルートディレクトリが指定されている → ルートに配置
                placement_locations.append(root_languages)
            else:
                # バージョンフォルダが指定されている → バージョンフォルダ内に配置
                for folder in folders:
                    if folder and folder != "/":
                        version_languages = os.path.join(mod_path, folder, "Languages")
                        placement_locations.append(version_languages)
        
        # 複数バージョン対応: 他のバージョンも確認
        for version_key, folders in load_folders_content.items():
            if version_key == f"v{current_version}":
                continue  # 現在のバージョンは既に処理済み
            
            # ルートディレクトリ（"/"）が指定されている場合
            if "/" in folders:
                # ルートディレクトリは既に追加済みなのでスキップ
                continue
            else:
                # バージョンフォルダが指定されている場合
                for folder in folders:
                    if folder and folder != "/":
                        version_languages = os.path.join(mod_path, folder, "Languages")
                        if version_languages not in placement_locations:
                            placement_locations.append(version_languages)
    
    # 3. デフォルト（ルートレベル）が含まれていない場合は追加
    if not placement_locations:
        placement_locations.append(root_languages)
    
    return placement_locations

def copy_japanese_to_locations(jp_dir, placement_locations, logger=None):
    """
    Japaneseフォルダを複数の配置場所にコピーする
    """
    success_count = 0
    total_count = len(placement_locations)
    
    for i, dest_languages_dir in enumerate(placement_locations):
        try:
            # Languagesディレクトリが存在しない場合は作成
            os.makedirs(dest_languages_dir, exist_ok=True)
            
            # Japaneseフォルダの配置先
            dest_jp_dir = os.path.join(dest_languages_dir, JP_DIR_NAME)
            
            # 既存のJapaneseフォルダがある場合は削除
            if os.path.exists(dest_jp_dir):
                shutil.rmtree(dest_jp_dir, onerror=force_remove)
            
            # Japaneseフォルダをコピー
            shutil.copytree(jp_dir, dest_jp_dir)
            
            if logger:
                logger.info(f"      -> 配置完了 ({i+1}/{total_count}): {dest_jp_dir}")
            
            success_count += 1
            
        except Exception as e:
            if logger:
                logger.error(f"      -> 配置失敗 ({i+1}/{total_count}): {dest_languages_dir} - {e}")
    
    return success_count, total_count

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