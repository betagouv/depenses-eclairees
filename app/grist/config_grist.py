import os

from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Récupérer les variables
URL_DOCS_GRIST = os.getenv("URL_DOCS_GRIST")
URL_TABLE_ATTACHMENTS = os.getenv("URL_TABLE_ATTACHMENTS")
URL_TABLE_ENGAGEMENTS = os.getenv("URL_TABLE_ENGAGEMENTS")
URL_TABLE_BATCH = os.getenv("URL_TABLE_BATCH")

URL_TABLE_TEST_CLASSIF = os.getenv("URL_TABLE_TEST_CLASSIF")
URL_TABLE_TEST_P530 = os.getenv("URL_TABLE_TEST_P530")

API_KEY_GRIST = os.getenv("API_KEY_GRIST")
