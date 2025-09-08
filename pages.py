import webbrowser
from config import STEAM_URL_FMT, RIM2GAME_URL_FMT

def open_mod_pages(mod_id):
    """MODのSteamページと2game.infoページを開く"""
    steam_url = STEAM_URL_FMT.format(mod_id)
    rim2game_url = RIM2GAME_URL_FMT.format(mod_id)
    webbrowser.open(steam_url)
    webbrowser.open(rim2game_url)

def open_steam_workshop(mod_id):
    """MODのSteam Workshopページを開く"""
    steam_url = STEAM_URL_FMT.format(mod_id)
    webbrowser.open(steam_url)