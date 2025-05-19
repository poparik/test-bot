import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = "sqlite://db.sqlite3"
VERIFICATION_TIMEOUT = 60  # 

# https://dzen.ru/a/X2TXPcgzhGodMUOP

FORBIDDEN_WORDS = [
 
    "казино", "выигрыш", "ставки", "букмекер", "заработок", "инвестиции",
    "быстрые деньги", "криптовалюта", "заработок без вложений", "бесплатно",
    "акция", "скидка", "распродажа", "бонус", "промокод", "регистрация",
    "вип", "эксклюзив"
]