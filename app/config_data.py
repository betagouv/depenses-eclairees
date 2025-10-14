import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Récupérer les variables
URL_DOCS_GRIST = os.getenv('URL_DOCS_GRIST')
URL_TABLE_ATTACHMENTS = os.getenv('URL_TABLE_ATTACHMENTS')
URL_TABLE_ENGAGEMENTS = os.getenv('URL_TABLE_ENGAGEMENTS')
API_KEY_GRIST = os.getenv('API_KEY_GRIST')

LOG_EXECUTION_TIME = os.getenv('LOG_EXECUTION_TIME', '').lower() in ('true', '1')
