class ProgressManager:
    """GUIのUI更新を管理し、別スレッドから安全に呼び出すためのクラス"""
    def __init__(self, gui):
        self.gui = gui

    def set_status(self, text):
        self.gui.set_status(text)

    def popup_info(self, message):
        self.gui.popup_info(message)

    def popup_error(self, message):
        self.gui.popup_error(message)

    def popup_warning(self, message):
        self.gui.popup_warning(message)

    def popup_retry_cancel(self, message):
        return self.gui.popup_retry_cancel(message)