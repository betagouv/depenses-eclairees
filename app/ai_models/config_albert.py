import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Récupérer les variables
BASE_URL_PROD = os.getenv('BASE_URL_PROD')
API_KEY_ALBERT = os.getenv('API_KEY_ALBERT')
API_KEY_AMA = os.getenv('API_KEY_AMA')