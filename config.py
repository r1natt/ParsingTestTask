import configparser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent # основная директория
CONFIG_PATH = BASE_DIR / "config.ini"

config = configparser.ConfigParser()
config.read(CONFIG_PATH)

USER = config["LOGIN"]["USER"]
PASSWORD = config["LOGIN"]["PASSWORD"]
