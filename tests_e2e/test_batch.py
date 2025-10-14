import sys
import os
import datetime
import json
from pathlib import Path

import pandas as pd
#from freezegun import freeze_time

from app import file_manager
from app import processor
from app.ai_models.config_albert import BASE_URL_PROD, API_KEY_ALBERT
from app.file_manager import DIC_CLASS_FILE_BY_NAME
from app.processor import ATTRIBUTES


batch_input_dir = sys.argv[1] if len(sys.argv) > 1 else "batch_input"

BASE_PATH = Path(__file__).parent.parent.absolute()
BASE_DATA_PATH = (BASE_PATH / "../data").absolute()
BASE_TEST_DATA_PATH = BASE_DATA_PATH / "tests"
BASE_EXPECTED_DATA_PATH = BASE_TEST_DATA_PATH / "batch_output"
BATCH_FOLDER_PATH = batch_input_dir

# Add poppler to path
os.environ['PATH'] = '/usr/local/bin:' + os.getenv('PATH', '')


def sort_dict_keys(d):
    items = sorted(list(d.items()))
    new_dict = {}
    for key, value in items:
        if isinstance(value, dict):
            value = sort_dict_keys(value)
        new_dict[key] = value
    return new_dict


def main():
    output_folder = BASE_TEST_DATA_PATH / f"runs/{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    os.makedirs(output_folder)
    output_folder_documents = output_folder / "documents"
    os.makedirs(output_folder_documents, exist_ok=True)
    output_folder_ejs = output_folder / "ejs"
    os.makedirs(output_folder_ejs, exist_ok=True)

    now = '2025-09-25'
    df = file_manager.get_files_initial_infos(
        BATCH_FOLDER_PATH,
        batch_grist='batch_test',
    )

    df = file_manager.classify_files(
        df,
        list_classification=DIC_CLASS_FILE_BY_NAME,
    )

    df = processor.df_extract_text(
        df,
        word_threshold=100,
        max_workers=4,
    )

    return

    max_mots = 20000
    embedding_model = "embeddings-small"

    df = processor.df_select_content(
        dfFiles=df,
        api_key=API_KEY_ALBERT,
        base_url=BASE_URL_PROD,
        embedding_model=embedding_model,
        dfAttributes=ATTRIBUTES,
        max_mots=max_mots,
    )

    llm_model = 'albert-large'
    df = processor.df_analyze_content(
        api_key=API_KEY_ALBERT,
        base_url=BASE_URL_PROD,
        llm_model=llm_model,
        df=df,
        dfAttributes=ATTRIBUTES,
        save_grist=False,
    )

    df.to_csv(output_folder / "00_output.csv", index=False)

    for _, row in df.iterrows():
        llm_response = row.llm_response
        if pd.isna(llm_response):
            data = {}
        else:
            data = json.loads(llm_response)
            data = sort_dict_keys(data)
        with open(output_folder_documents / f"{row.filename}.json", 'w') as f:
            json.dump(data, f, indent=4)

    df_ejs = processor.final_infos_all_EJ(
        df,
        api_key=API_KEY_ALBERT,
        api_url=BASE_URL_PROD,
        llm_model='albert-large',
        max_workers=25,
    )

    # Only keep required columns
    columns = [
        "num_EJ",
        "Designation",
        "Descriptif_prestations",
        "Date",
        "Prestataire",
        "Administration",
        "SIRET",
    ]
    df_ejs = df_ejs[columns]

    # Store ejs
    for data in df_ejs.to_dict("records"):
        data = sort_dict_keys(data)
        with open(output_folder_ejs / f"{data['num_EJ']}.json", 'w') as f:
            json.dump(data, f, indent=4)


if __name__ == "__main__":
    main()
