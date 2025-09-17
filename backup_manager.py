import os
import shutil
import datetime
import filecmp
from collections import defaultdict

from config import MODS_DIR, LOCAL_MODS_DIR, BACKUP_ROOT, LOGS_DIR
from utils import get_mod_name_from_xml, sanitize_filename
from logger import get_logger


# mod_comparator.pyの機能を統合
def are_dirs_equal(dir1, dir2, logger=None, pman=None):
    """2つのディレクトリの内容が同じか高速に比較する（ハッシュベース最適化版）"""
    if not os.path.isdir(dir1) or not os.path.isdir(dir2):
        return False
    
    try:
        # ハッシュベースの高速比較
        return _compare_dirs_with_hash(dir1, dir2, logger, pman)
    except Exception as e:
        # エラーが発生した場合は従来の方法で比較
        return _detailed_dir_comparison(dir1, dir2)

def _compare_dirs_with_hash(dir1, dir2, logger=None, pman=None):
    """ハッシュベースの高速ディレクトリ比較"""
    import hashlib
    import time
    
    # ディレクトリのハッシュを計算
    hash1 = _calculate_dir_hash(dir1, logger, pman)
    hash2 = _calculate_dir_hash(dir2, logger, pman)
    
    return hash1 == hash2

def _calculate_dir_hash(dir_path, logger=None, pman=None):
    """ディレクトリ全体のハッシュを計算（ファイル内容も含む）"""
    import hashlib
    import os
    import time
    
    hasher = hashlib.md5()
    
    # ファイルパスをソートして一意性を保つ
    file_paths = []
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, dir_path)
            file_paths.append(rel_path)
    
    file_paths.sort()
    total_files = len(file_paths)
    start_time = time.time()
    
    if logger and total_files > 100:  # 100ファイル以上の場合のみ進捗表示
        logger.info(f"      -> ハッシュ計算進捗: 0/{total_files:,}ファイル (0.00%)")
    
    for i, rel_path in enumerate(file_paths):
        full_path = os.path.join(dir_path, rel_path)
        try:
            # ファイルパスをハッシュに追加
            hasher.update(rel_path.encode('utf-8'))
            
            # ファイルサイズをハッシュに追加
            file_size = os.path.getsize(full_path)
            hasher.update(str(file_size).encode('utf-8'))
            
            # ファイルの修正時間をハッシュに追加
            mtime = os.path.getmtime(full_path)
            hasher.update(str(mtime).encode('utf-8'))
            
            # 小さいファイル（1MB以下）は内容もハッシュに含める
            if file_size <= 1024 * 1024:  # 1MB
                with open(full_path, 'rb') as f:
                    # ファイルの先頭と末尾の一部を読み取る（高速化）
                    chunk_size = min(8192, file_size)
                    if file_size > 0:
                        f.seek(0)
                        chunk = f.read(chunk_size)
                        hasher.update(chunk)
                        
                        # ファイルが大きい場合は末尾も読み取る
                        if file_size > chunk_size * 2:
                            f.seek(-chunk_size, 2)
                            chunk = f.read(chunk_size)
                            hasher.update(chunk)
            
        except (OSError, IOError):
            # ファイルが読めない場合はパスとサイズのみでハッシュ
            hasher.update(rel_path.encode('utf-8'))
            hasher.update(b'0')  # サイズ0として扱う
        
        # 進捗表示（100ファイルごと、または最後のファイル）
        if total_files > 100 and (i + 1) % 100 == 0 or i == total_files - 1:
            elapsed = time.time() - start_time
            progress = (i + 1) / total_files * 100
            files_per_sec = (i + 1) / elapsed if elapsed > 0 else 0
            
            # ログに進捗を記録
            if logger:
                logger.info(f"      -> ハッシュ計算進捗: {i+1:,}/{total_files:,}ファイル ({progress:.1f}%) - {files_per_sec:.1f}ファイル/秒")
            
            # GUIに進捗を表示
            if pman:
                pman.set_status(f"ハッシュ計算中: {i+1:,}/{total_files:,}ファイル ({progress:.1f}%) - {files_per_sec:.1f}ファイル/秒")
    
    total_elapsed = time.time() - start_time
    if total_files > 0:
        files_per_sec = total_files / total_elapsed if total_elapsed > 0 else 0
        
        # ログに完了情報を記録
        if logger:
            logger.info(f"      -> ハッシュ計算完了: {total_files:,}ファイル, {total_elapsed:,.2f}秒 ({files_per_sec:.1f}ファイル/秒)")
        
        # GUIに完了情報を表示
        if pman:
            pman.set_status(f"ハッシュ計算完了: {total_files:,}ファイル ({total_elapsed:,.2f}秒)")
    
    return hasher.hexdigest()

def _detailed_dir_comparison(dir1, dir2):
    """詳細なディレクトリ比較（フォールバック用）"""
    try:
        dcmp = filecmp.dircmp(dir1, dir2)
        if dcmp.diff_files or dcmp.left_only or dcmp.right_only:
            return False
        
        for sub_dcmp in dcmp.subdirs.values():
            if not _detailed_dir_comparison(sub_dcmp.left, sub_dcmp.right):
                return False
                
        return True
    except Exception:
        return False

class ModStatus:
    """MODの比較結果を表すステータス"""
    UNCHANGED = "UNCHANGED"
    DUPLICATE = "DUPLICATE"
    NEEDS_BACKUP = "NEEDS_BACKUP"

def compare_mod_versions(mod_info, historical_mods, copied_versions_by_id, logger, pman=None):
    """
    MODを過去のバックアップと現在の実行ですでにコピーされたものと比較する.
    
    Returns:
        ModStatus: 比較結果のステータス
    """
    import time
    current_path = mod_info['path']
    mod_id = mod_info['mod_id']
    
    # ファイル数を事前にチェック
    try:
        file_count = sum(len(files) for root, dirs, files in os.walk(current_path))
        logger.info(f"  -> MODファイル数: {file_count:,}個")
        if pman:
            pman.set_status(f"MOD比較中: {file_count:,}ファイル")
    except Exception:
        file_count = 0
    
    # ステップ1: 過去のバックアップとの比較
    logger.info("  -> ステップ1: 過去のバックアップとの比較を開始...")
    if mod_id in historical_mods:
        total_backups = len(historical_mods[mod_id])
        for i, old_path in enumerate(historical_mods[mod_id]):
            backup_name = os.path.basename(old_path)
            logger.info(f"    -> 比較中 ({i+1:,}/{total_backups:,}): {backup_name}")
            if pman:
                pman.set_status(f"バックアップ比較中 ({i+1:,}/{total_backups:,}): {backup_name}")
            start_time = time.time()
            
            # ハッシュ計算の進捗を表示
            logger.info(f"    -> ハッシュ計算中...")
            if pman:
                pman.set_status(f"ハッシュ計算中 ({i+1:,}/{total_backups:,}): {backup_name}")
            hash_start = time.time()
            if are_dirs_equal(current_path, old_path, logger, pman):
                hash_elapsed = time.time() - hash_start
                total_elapsed = time.time() - start_time
                logger.info(f"    -> 結果: 同一のバージョンを過去のバックアップで発見しました。({old_path})")
                logger.info(f"    -> ハッシュ計算時間: {hash_elapsed:,.2f}秒, 総比較時間: {total_elapsed:,.2f}秒")
                if pman:
                    pman.set_status(f"同一バージョン発見: {backup_name} ({total_elapsed:,.2f}秒)")
                return ModStatus.UNCHANGED
            else:
                hash_elapsed = time.time() - hash_start
                total_elapsed = time.time() - start_time
                logger.info(f"    -> 結果: 内容が異なります")
                logger.info(f"    -> ハッシュ計算時間: {hash_elapsed:,.2f}秒, 総比較時間: {total_elapsed:,.2f}秒")
        logger.info("    -> 結果: 過去のバックアップに同一バージョンはありませんでした。")
        if pman:
            pman.set_status("過去のバックアップに同一バージョンなし")
    else:
        logger.info("    -> 結果: このMODの過去のバックアップはありません。")
        if pman:
            pman.set_status("過去のバックアップなし")

    # ステップ2: 今回の実行内での重複チェック
    logger.info("  -> ステップ2: 今回の実行内での重複チェックを開始...")
    if mod_id in copied_versions_by_id:
        total_copied = len(copied_versions_by_id[mod_id])
        for i, copied_path in enumerate(copied_versions_by_id[mod_id]):
            copied_name = os.path.basename(copied_path)
            logger.info(f"    -> 比較中 ({i+1:,}/{total_copied:,}): {copied_name}")
            if pman:
                pman.set_status(f"重複チェック中 ({i+1:,}/{total_copied:,}): {copied_name}")
            start_time = time.time()
            
            # ハッシュ計算の進捗を表示
            logger.info(f"    -> ハッシュ計算中...")
            if pman:
                pman.set_status(f"ハッシュ計算中 ({i+1:,}/{total_copied:,}): {copied_name}")
            hash_start = time.time()
            if are_dirs_equal(current_path, copied_path, logger, pman):
                hash_elapsed = time.time() - hash_start
                total_elapsed = time.time() - start_time
                logger.info(f"    -> 結果: 同一内容のバージョンが今回の処理で既にバックアップ済みです。({copied_path})")
                logger.info(f"    -> ハッシュ計算時間: {hash_elapsed:,.2f}秒, 総比較時間: {total_elapsed:,.2f}秒")
                if pman:
                    pman.set_status(f"重複発見: {copied_name} ({total_elapsed:,.2f}秒)")
                return ModStatus.DUPLICATE
            else:
                hash_elapsed = time.time() - hash_start
                total_elapsed = time.time() - start_time
                logger.info(f"    -> 結果: 内容が異なります")
                logger.info(f"    -> ハッシュ計算時間: {hash_elapsed:,.2f}秒, 総比較時間: {total_elapsed:,.2f}秒")
        logger.info("    -> 結果: 今回バックアップ済みのバージョンとは内容が異なります。")
        if pman:
            pman.set_status("重複なし - バックアップ必要")
    else:
        logger.info("    -> 結果: このMOD IDは今回の実行で初めて処理されます。")
        if pman:
            pman.set_status("初回処理 - バックアップ必要")

    return ModStatus.NEEDS_BACKUP




def get_all_backups(backup_root):
    """すべてのバックアップフォルダのパスを新しい順で返す"""
    if not os.path.isdir(backup_root):
        return []

    backups = [d for d in os.listdir(backup_root) if
               os.path.isdir(os.path.join(backup_root, d)) and d.startswith("backup_")]
    backups.sort(reverse=True)

    return [os.path.join(backup_root, b) for b in backups]


def backup_mods(pman):
    """差分を考慮してMODをバックアップし、詳細なログを記録する。"""
    logger = get_logger("BackupManager")

    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    new_backup_dir = os.path.join(BACKUP_ROOT, f"backup_{now_str}")

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
                logger.warning(
                    f"重複検出: MOD ID '{mod_id}' は [{', '.join(source_names)}] に存在します。各々を比較対象とします。")
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

            status = compare_mod_versions(mod_info, historical_mods, copied_versions_by_id, logger, pman)

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
            summary_lines = [f"バックアップが完了しました。\n", f"新規: {len(new_mods_list)}個",
                             f"更新: {len(updated_mods_list)}個", f"変更なし: {unchanged_count}個"]
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