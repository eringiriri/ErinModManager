import os
import logging
from datetime import datetime
from config import LOGS_DIR

class ErinModManagerLogger:
    """統一されたログ管理クラス"""
    
    _instance = None
    _logger = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._logger is None:
            self._setup_logger()
    
    def _setup_logger(self):
        """ログ設定（起動時に一度だけ実行）"""
        os.makedirs(LOGS_DIR, exist_ok=True)
        log_file = os.path.join(LOGS_DIR, f"ErinModManager_{datetime.now().strftime('%y.%m.%d_%H.%M.%S')}.log")
        
        # 既存のロガーをクリア
        for logger_name in ['RimWorldJapanizer', 'AutoJapanizer', 'TranslationChecker', 'TranslationScraper', 'BackupManager']:
            logger = logging.getLogger(logger_name)
            if logger.hasHandlers():
                logger.handlers.clear()
        
        # メインロガーを設定
        self._logger = logging.getLogger("ErinModManager")
        if self._logger.hasHandlers():
            self._logger.handlers.clear()
            
        self._logger.setLevel(logging.INFO)
        handler = logging.FileHandler(log_file, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)
        
        # 各モジュール用のロガーも同じファイルに出力
        for logger_name in ['RimWorldJapanizer', 'AutoJapanizer', 'TranslationChecker', 'TranslationScraper', 'BackupManager']:
            module_logger = logging.getLogger(logger_name)
            module_logger.setLevel(logging.INFO)
            module_logger.addHandler(handler)
            module_logger.propagate = False  # 重複出力を防ぐ
    
    def get_logger(self, module_name="ErinModManager"):
        """指定されたモジュール名のロガーを取得"""
        return logging.getLogger(module_name)
    
    def info(self, message, module_name="ErinModManager"):
        """INFOレベルのログを出力"""
        logger = logging.getLogger(module_name)
        logger.info(message)
    
    def warning(self, message, module_name="ErinModManager"):
        """WARNINGレベルのログを出力"""
        logger = logging.getLogger(module_name)
        logger.warning(message)
    
    def error(self, message, module_name="ErinModManager"):
        """ERRORレベルのログを出力"""
        logger = logging.getLogger(module_name)
        logger.error(message)
    
    def debug(self, message, module_name="ErinModManager"):
        """DEBUGレベルのログを出力"""
        logger = logging.getLogger(module_name)
        logger.debug(message)

# グローバルインスタンス
logger_manager = ErinModManagerLogger()

def get_logger(module_name="ErinModManager"):
    """指定されたモジュール名のロガーを取得する便利関数"""
    return logger_manager.get_logger(module_name)
