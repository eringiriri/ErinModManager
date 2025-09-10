import os

MODS_DIR = r"S:\SteamLibrary\steamapps\workshop\content\294100"
LOCAL_MODS_DIR = r"S:\SteamLibrary\steamapps\common\RimWorld\Mods"
JAPANIZED_DIR = os.path.join(os.path.dirname(MODS_DIR), "japanized")
TMP_DIR = os.path.join(JAPANIZED_DIR, "TMP")
OLD_DIR = os.path.join(JAPANIZED_DIR, "old")

# バックアップ保存先ルートディレクトリ
BACKUP_ROOT = os.path.join(JAPANIZED_DIR, "backup")
# ログ保存先ディレクトリを追加
LOGS_DIR = os.path.join(BACKUP_ROOT, "logs")

LANG_DIR_NAME = "Languages"
JP_DIR_NAME = "Japanese"
ZIP_FILENAME_FMT = "{}_download.zip"
UNPACK_DIR_FMT = "{}_unpack"

WINDOW_TITLE = "RimWorld MOD 日本語化インストーラー"
WINDOW_SIZE = "520x240"
LABEL_DESCRIPTION = "日本語化パックのURLを入力し、Enterを押してください。"
ENTRY_WIDTH = 70
LABEL_STATUS_COLOR = "#007000"

STEAM_URL_FMT = "https://steamcommunity.com/sharedfiles/filedetails/?id={}"
RIM2GAME_URL_FMT = "https://rimworld.2game.info/detail.php?id={}"

REFERER_FMT = "https://rimworld.2game.info/detail.php?id={}"
USER_AGENT = "RimWorldJapanizer/1.0 (+https://rimworld.2game.info)"
CHUNK_SIZE = 1024 * 100
TIMEOUT = 30