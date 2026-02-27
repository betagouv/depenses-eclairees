# Assets pour les tests d'extraction

- **Lettre** : générer les formats alternatifs (doc, docx, odt, etc.) depuis `./generate_docs.sh`.
- **Excel** : générer les fichiers de test XLSX, XLS, ODS (plusieurs onglets, cellules fusionnées) avec :
  ```bash
  python tests/docia/file_processing/processor/text_extraction/assets/documents/generate_excel_assets.py
  ```
  Crée `sample.xlsx`, `sample.xls`, `sample.ods` dans ce répertoire. Nécessite `openpyxl`, `odfpy` et `xlwt` (groupe dev).
