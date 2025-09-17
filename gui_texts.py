# GUI Text Constants
# このファイルにはGUIで使用されるすべてのテキストを定義します

# ステータス表示
READY_STATUS = "準備完了"
INPUT_CHECKING_STATUS = "入力値確認中…"
STARTUP_CHECKING_STATUS = "起動時更新チェック中..."
TRANSLATION_UPDATE_START_STATUS = "翻訳リスト更新開始"
FULL_SCRAPE_START_STATUS = "全ページ取得開始"
MOD_BACKUP_START_STATUS = "MODバックアップ開始"
AUTO_JAPANIZATION_START_STATUS = "一括日本語化開始"

# フレームタイトル
MAIN_OPERATIONS_FRAME_TITLE = "メイン操作"
FOLDER_FRAME_TITLE = "フォルダを開く"

# ボタンテキスト
EXECUTE_BUTTON_TEXT = "実行"
BACKUP_BUTTON_TEXT = "MODバックアップ"
UPDATE_CHECK_BUTTON_TEXT = "更新チェック"
FULL_SCRAPE_BUTTON_TEXT = "📥 全ページ取得"
APPLY_ALL_JP_BUTTON_TEXT = "一括日本語化適用"
DELETE_CSV_BUTTON_TEXT = "CSV削除"

# フォルダボタンテキスト
WORKSHOP_MODS_BUTTON_TEXT = "ワークショップMOD"
LOCAL_MODS_BUTTON_TEXT = "ローカルMOD"
BACKUP_FOLDER_BUTTON_TEXT = "バックアップ"

# エラーメッセージ
URL_EMPTY_ERROR = "URLが空です。"
MOD_ID_EXTRACTION_ERROR = "MOD IDがURLから取得できませんでした。"
ARCHIVE_FORMAT_ERROR = "ダウンロードファイルがアーカイブ形式ではありません。\nMOD配布ページを開きます。"
JAPANESE_FOLDER_NOT_FOUND_ERROR = "Japaneseフォルダが見つかりません。"
MOD_FOLDER_NOT_DETECTED_STATUS = "MODフォルダ未検出。Steamページを開きます。"
WEBSITE_OPEN_ERROR = "ウェブサイトを開けませんでした。\n{}"
CSV_DELETE_ERROR = "CSVファイルの削除に失敗しました。\n{}"

# 警告メッセージ
PROCESS_RUNNING_WARNING = "現在、別の処理が実行中です。"
CSV_NOT_EXISTS_WARNING = "CSVファイルが存在しません。\n「全ページ取得」ボタンで新規作成してください。"
CSV_NOT_EXISTS_INFO = "CSVファイルは存在しません。"

# 情報メッセージ
FULL_SCRAPE_COMPLETE_INFO = "全ページ取得が完了しました。\n「一括日本語ファイル適用」ボタンで適用できます。"
CSV_DELETE_SUCCESS_INFO = "CSVファイルを削除しました。"

# 確認ダイアログ
TRANSLATION_UPDATE_DETECTED_TITLE = "翻訳更新検出"
TRANSLATION_UPDATE_DETECTED_MESSAGE = "新しい翻訳ファイルが {} 件見つかりました。\n\n翻訳リストを更新しますか？\n\n※「いいえ」を選択しても、後から「更新チェック」ボタンで更新できます。"
CSV_DELETE_CONFIRM_TITLE = "確認"
CSV_DELETE_CONFIRM_MESSAGE = "CSVファイルを削除しますか？\n\n削除後は「最新翻訳チェック」で新規作成できます。"

# フォルダ名（open_folder関数で使用）
WORKSHOP_MODS_FOLDER_NAME = "ワークショップMODフォルダ"
LOCAL_MODS_FOLDER_NAME = "ローカルMODフォルダ"
BACKUP_FOLDER_NAME = "バックアップフォルダ"

# ログメッセージ
APP_STARTUP_LOG = "=== RimWorld Japanizer 起動 ==="
APP_SHUTDOWN_LOG = "=== RimWorld Japanizer 終了 ==="
WORKSHOP_MODS_OPEN_LOG = "ワークショップMODフォルダを開く"
LOCAL_MODS_OPEN_LOG = "ローカルMODフォルダを開く"
BACKUP_FOLDER_OPEN_LOG = "バックアップフォルダを開く"
WEBSITE_OPEN_LOG = "rimworld.2game.infoサイトを開く"
WEBSITE_OPEN_ERROR_LOG = "ウェブサイトを開けませんでした: {}"
INDIVIDUAL_INSTALL_START_LOG = "個別インストール開始: URL={}"
INDIVIDUAL_INSTALL_PROCESS_START_LOG = "個別インストール処理開始: URL={}"
INDIVIDUAL_INSTALL_PROCESS_COMPLETE_LOG = "個別インストール処理完了"
INDIVIDUAL_INSTALL_PROCESS_ERROR_LOG = "個別インストール処理中にエラー: {}"
MOD_BACKUP_START_LOG = "MODバックアップ開始"
MOD_BACKUP_PROCESS_START_LOG = "MODバックアップ処理開始"
MOD_BACKUP_PROCESS_COMPLETE_LOG = "MODバックアップ処理完了"
MOD_BACKUP_PROCESS_ERROR_LOG = "MODバックアップ処理中にエラー: {}"
AUTO_JAPANIZATION_START_LOG = "一括日本語化開始"
AUTO_JAPANIZATION_PROCESS_START_LOG = "一括日本語化処理開始"
AUTO_JAPANIZATION_PROCESS_COMPLETE_LOG = "一括日本語化処理完了"
AUTO_JAPANIZATION_PROCESS_ERROR_LOG = "一括日本語化処理中にエラー: {}"
TRANSLATION_UPDATE_START_LOG = "翻訳リスト更新開始"
CSV_UPDATE_PROCESS_START_LOG = "CSV更新処理開始"
CSV_UPDATE_PROCESS_COMPLETE_LOG = "CSV更新処理完了"
CSV_UPDATE_PROCESS_ERROR_LOG = "CSV更新処理中にエラー: {}"
FULL_SCRAPE_START_LOG = "全ページ取得開始"
FULL_SCRAPE_PROCESS_START_LOG = "全ページ取得処理開始"
FULL_SCRAPE_PROCESS_COMPLETE_LOG = "全ページ取得処理完了"
FULL_SCRAPE_PROCESS_ERROR_LOG = "全ページ取得処理中にエラー: {}"
CSV_NOT_EXISTS_SKIP_LOG = "CSVファイルが存在しないため更新チェックをスキップ"
STARTUP_CHECK_START_LOG = "起動時更新チェック開始"
STARTUP_CHECK_SKIP_LOG = "CSVファイルが存在しないため起動時チェックをスキップ"
STARTUP_CHECK_ERROR_LOG = "起動時更新チェック中にエラー: {}"
BACKGROUND_CHECK_START_LOG = "バックグラウンド更新チェック開始"
NO_NEW_TRANSLATIONS_LOG = "新しい翻訳ファイルは見つかりませんでした"
NEW_TRANSLATIONS_FOUND_LOG = "新しい翻訳ファイルを {} 件発見"
BACKGROUND_CHECK_ERROR_LOG = "バックグラウンド更新チェック中にエラー: {}"
CSV_UPDATE_DIALOG_LOG = "CSV更新確認ダイアログ表示: {}件の新しい翻訳ファイル"
USER_SELECTED_CSV_UPDATE_LOG = "ユーザーがCSV更新を選択"
USER_CANCELLED_CSV_UPDATE_LOG = "ユーザーがCSV更新をキャンセル"
