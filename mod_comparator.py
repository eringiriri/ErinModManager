import os
import filecmp

def are_dirs_equal(dir1, dir2):
    """2つのディレクトリの内容が同じか高速に比較する"""
    if not os.path.isdir(dir1) or not os.path.isdir(dir2):
        return False
        
    dcmp = filecmp.dircmp(dir1, dir2)
    if dcmp.diff_files or dcmp.left_only or dcmp.right_only:
        return False
    
    for sub_dcmp in dcmp.subdirs.values():
        if not are_dirs_equal(sub_dcmp.left, sub_dcmp.right):
            return False
            
    return True

class ModStatus:
    """MODの比較結果を表すステータス"""
    UNCHANGED = "UNCHANGED"
    DUPLICATE = "DUPLICATE"
    NEEDS_BACKUP = "NEEDS_BACKUP"

def compare_mod_versions(mod_info, historical_mods, copied_versions_by_id, logger):
    """
    MODを過去のバックアップと現在の実行ですでにコピーされたものと比較する.
    
    Returns:
        ModStatus: 比較結果のステータス
    """
    current_path = mod_info['path']
    mod_id = mod_info['mod_id']
    
    # ステップ1: 過去のバックアップとの比較
    logger.info("  -> ステップ1: 過去のバックアップとの比較を開始...")
    if mod_id in historical_mods:
        for old_path in historical_mods[mod_id]:
            if are_dirs_equal(current_path, old_path):
                logger.info(f"    -> 結果: 同一のバージョンを過去のバックアップで発見しました。({old_path})")
                return ModStatus.UNCHANGED
        logger.info("    -> 結果: 過去のバックアップに同一バージョンはありませんでした。")
    else:
        logger.info("    -> 結果: このMODの過去のバックアップはありません。")

    # ステップ2: 今回の実行内での重複チェック
    logger.info("  -> ステップ2: 今回の実行内での重複チェックを開始...")
    if mod_id in copied_versions_by_id:
        for copied_path in copied_versions_by_id[mod_id]:
            if are_dirs_equal(current_path, copied_path):
                logger.info(f"    -> 結果: 同一内容のバージョンが今回の処理で既にバックアップ済みです。({copied_path})")
                return ModStatus.DUPLICATE
        logger.info("    -> 結果: 今回バックアップ済みのバージョンとは内容が異なります。")
    else:
        logger.info("    -> 結果: このMOD IDは今回の実行で初めて処理されます。")

    return ModStatus.NEEDS_BACKUP