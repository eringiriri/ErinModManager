import os
import requests
import zipfile
import shutil
import datetime
import logging
from collections import defaultdict

from config import REFERER_FMT, USER_AGENT, CHUNK_SIZE, TIMEOUT
from config import MODS_DIR, LOCAL_MODS_DIR, BACKUP_ROOT, LOGS_DIR
from utils import get_mod_name_from_xml, sanitize_filename
from mod_comparator import ModStatus, compare_mod_versions

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

def setup_logger(log_name):
    """バックアップ処理用のロガーをセットアップする"""
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_file = os.path.join(LOGS_DIR, f"{log_name}.log")
    
    logger = logging.getLogger(log_name)
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_file, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def get_all_backups(backup_root):
    """すべてのバックアップフォルダのパスを新しい順で返す"""
    if not os.path.isdir(backup_root):
        return []
    
    backups = [d for d in os.listdir(backup_root) if os.path.isdir(os.path.join(backup_root, d)) and d.startswith("backup_")]
    backups.sort(reverse=True)
    
    return [os.path.join(backup_root, b) for b in backups]

def backup_mods(pman):
    """差分を考慮してMODをバックアップし、詳細なログを記録する。"""
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_name = f"backup_{now_str}"
    logger = setup_logger(log_name)
    
    new_backup_dir = os.path.join(BACKUP_ROOT, log_name)

    try:
        logger.info("================ バックアップ処理開始 ================")
        pman.set_status("バックアップ準備中…")
        os.makedirs(BACKUP_ROOT, exist_ok=True)
        
        os.makedirs(new_backup_dir)
        logger.info(f"一時バックアップフォルダを作成しました: {new_backup_dir}")

        # 1. 現在のMOD情報を収集
        logger.info("--- フェーズ1: 現行MODのスキャン開始 ---")
        mods_by_id = defaultdict(list)
        for name, path in [("Workshop", MODS_DIR), ("Local", LOCAL_MODS_DIR)]:
            logger.info(f"スキャン中: {path} ({name})")
            if os.path.isdir(path):
                found_mods_count = 0
                for original_folder_name in os.listdir(path):
                    mod_path = os.path.join(path, original_folder_name)
                    if os.path.isdir(mod_path):
                        sanitized_id = sanitize_filename(original_folder_name)
                        if original_folder_name != sanitized_id:
                            logger.info(f"フォルダ名をサニタイズしました: '{original_folder_name}' -> '{sanitized_id}'")

                        display_name_base = get_mod_name_from_xml(mod_path) or original_folder_name
                        display_name = f"{display_name_base} ({name})"
                        
                        mods_by_id[sanitized_id].append({
                            "mod_id": sanitized_id,
                            "path": mod_path,
                            "type": name,
                            "display_name": display_name
                        })
                        found_mods_count += 1
                logger.info(f"  -> {found_mods_count} 個のMODフォルダを検出しました。")

        current_mods_list = []
        for mod_id, mods in mods_by_id.items():
            if len(mods) > 1:
                source_names = [m['type'] for m in mods]
                logger.warning(f"重複検出: MOD ID '{mod_id}' は [{', '.join(source_names)}] に存在します。各々を比較対象とします。")
            current_mods_list.extend(mods)
        logger.info(f"合計 {len(current_mods_list)} 個のMODをスキャン対象とします。")
        logger.info("--- フェーズ1: 現行MODのスキャン完了 ---")
        
        # 2. 過去の全バックアップからMOD情報を収集
        logger.info("--- フェーズ2: 過去バックアップのスキャン開始 ---")
        all_backup_dirs = get_all_backups(BACKUP_ROOT)
        all_backup_dirs = [d for d in all_backup_dirs if os.path.basename(d) != os.path.basename(new_backup_dir)]
        logger.info(f"検出した過去のバックアップ数: {len(all_backup_dirs)}件")

        historical_mods = defaultdict(list)
        if all_backup_dirs:
            for backup_dir in all_backup_dirs:
                for type_name in os.listdir(backup_dir):
                    type_path = os.path.join(backup_dir, type_name)
                    if os.path.isdir(type_path):
                        for mod_id_folder in os.listdir(type_path):
                            historical_mods[mod_id_folder].append(os.path.join(type_path, mod_id_folder))
        logger.info(f"過去のバックアップから {len(historical_mods)} 個のユニークなMOD IDの情報を収集しました。")
        logger.info("--- フェーズ2: 過去バックアップのスキャン完了 ---")

        # 3. 比較とコピー処理
        logger.info("--- フェーズ3: 比較とバックアップ実行開始 ---")
        total_mods = len(current_mods_list)
        new_mods_list, updated_mods_list = [], []
        unchanged_count, skipped_duplicate_count = 0, 0
        copied_versions_by_id = defaultdict(list)

        for idx, mod_info in enumerate(current_mods_list):
            mod_id, current_path, mod_type, display_name = mod_info.values()
            
            logger.info(f"==> 処理中 ({idx + 1}/{total_mods}): {display_name} [{mod_id}]")
            pman.set_status(f"({idx + 1}/{total_mods}) 比較中: {display_name}")

            status = compare_mod_versions(mod_info, historical_mods, copied_versions_by_id, logger)

            logger.info("  -> ステップ3: 最終判断")
            if status == ModStatus.UNCHANGED:
                unchanged_count += 1
                logger.info("    -> 判断: 変更なし (過去のバックアップと同一)。スキップします。")
            elif status == ModStatus.DUPLICATE:
                skipped_duplicate_count += 1
                logger.info("    -> 判断: 重複スキップ (今回の他バージョンと同一)。スキップします。")
            elif status == ModStatus.NEEDS_BACKUP:
                logger.info("    -> 判断: バックアップが必要です。コピー処理を開始します。")
                dest_dir = os.path.join(new_backup_dir, mod_type, mod_id)
                os.makedirs(os.path.dirname(dest_dir), exist_ok=True)
                
                shutil.copytree(current_path, dest_dir)
                logger.info(f"      コピー完了: {current_path} -> {dest_dir}")
                
                copied_versions_by_id[mod_id].append(current_path)

                if mod_id in historical_mods:
                    updated_mods_list.append(display_name)
                    logger.info("    -> 分類: 更新")
                else:
                    new_mods_list.append(display_name)
                    logger.info("    -> 分類: 新規")
            
            logger.info(f"==> {display_name} の処理完了。")

        # 4. 結果報告と後処理
        logger.info("--- フェーズ4: 結果集計 ---")
        if not new_mods_list and not updated_mods_list:
            pman.set_status("変更なし。バックアップは作成されませんでした。")
            logger.info("新規・更新されたMODはなかったため、バックアップフォルダを削除します。")
            shutil.rmtree(new_backup_dir)
            pman.popup_info("更新されたMODはありませんでした。\n新しいバックアップは作成されませんでした。")
        else:
            summary_lines = [f"バックアップが完了しました。\n", f"新規: {len(new_mods_list)}個", f"更新: {len(updated_mods_list)}個", f"変更なし: {unchanged_count}個"]
            log_summary = f"バックアップ結果: 新規 {len(new_mods_list)}, 更新 {len(updated_mods_list)}, 変更なし {unchanged_count}, 重複スキップ {skipped_duplicate_count}"
            logger.info(log_summary)

            if new_mods_list:
                summary_lines.extend(["\n--- 新規MODリスト ---", ", ".join(new_mods_list)])
                logger.info(f"新規MODリスト: {', '.join(new_mods_list)}")
            if updated_mods_list:
                summary_lines.extend(["\n--- 更新MODリスト ---", ", ".join(updated_mods_list)])
                logger.info(f"更新MODリスト: {', '.join(updated_mods_list)}")

            pman.set_status("バックアップ完了！")
            pman.popup_info("\n".join(summary_lines))
        logger.info("--- フェーズ4: 結果集計完了 ---")

    except Exception as e:
        logger.exception(f"バックアップ中に予期しないエラーが発生しました。エラー: {e}")
        if os.path.exists(new_backup_dir):
            shutil.rmtree(new_backup_dir)
            logger.warning(f"エラー発生のため、不完全なバックアップフォルダを削除しました: {new_backup_dir}")
        pman.set_status("バックアップ失敗。")
        pman.popup_error(f"バックアップ中にエラーが発生しました。\n{e}")
    finally:
        logger.info("================ バックアップ処理終了 ================")
        logging.shutdown()