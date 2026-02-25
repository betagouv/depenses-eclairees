#!/usr/bin/env python3
"""
Génère les fichiers de test Excel (XLSX, XLS, ODS) avec plusieurs onglets et cellules fusionnées.
À exécuter depuis la racine du projet ou depuis ce répertoire :
  python tests/docia/file_processing/processor/extraction_text_from_attachments/assets/documents/generate_excel_assets.py
Les fichiers sample.xlsx, sample.xls, sample.ods sont créés dans ce répertoire.
"""
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent


def write_xlsx():
    """Crée sample.xlsx avec 2 onglets et cellules fusionnées (openpyxl)."""
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    # Feuille 1
    ws1 = wb.active
    ws1.title = "Feuille1"
    ws1["A1"] = "Titre fusionné"
    ws1.merge_cells("A1:B1")
    ws1["A2"], ws1["B2"] = "Col A", "Col B"
    ws1["A3"], ws1["B3"] = "Ligne 1", "10"
    ws1["A4"], ws1["B4"] = "Ligne 2", "20"
    ws1.merge_cells("A5:B5")  # fusion horizontale
    ws1["A5"] = "Total"
    # Feuille 2
    ws2 = wb.create_sheet("Feuille2")
    ws2["A1"] = "Section"
    ws2.merge_cells("A1:A3")  # fusion verticale -> doit donner # en A2, A3
    ws2["B1"], ws2["B2"], ws2["B3"] = "V1", "V2", "V3"
    ws2["A4"] = "Fin"
    wb.save(OUT_DIR / "sample.xlsx")
    print("Créé:", OUT_DIR / "sample.xlsx")


def write_xls():
    """Crée sample.xls avec 2 onglets et cellules fusionnées (xlwt)."""
    try:
        import xlwt
    except ImportError:
        print("xlwt non installé (pip install xlwt). sample.xls non généré.")
        return
    wb = xlwt.Workbook()
    # Feuille 1
    ws1 = wb.add_sheet("Feuille1")
    ws1.write_merge(0, 0, 0, 1, "Titre fusionné")
    ws1.write(1, 0, "Col A")
    ws1.write(1, 1, "Col B")
    ws1.write(2, 0, "Ligne 1")
    ws1.write(2, 1, 10)
    ws1.write(3, 0, "Ligne 2")
    ws1.write(3, 1, 20)
    ws1.write_merge(4, 4, 0, 1, "Total")
    # Feuille 2
    ws2 = wb.add_sheet("Feuille2")
    ws2.write_merge(0, 2, 0, 0, "Section")  # fusion verticale (ne pas écrire dans les cellules fusionnées)
    ws2.write(0, 1, "V1")
    ws2.write(1, 1, "V2")
    ws2.write(2, 1, "V3")
    ws2.write(3, 0, "Fin")
    wb.save(str(OUT_DIR / "sample.xls"))
    print("Créé:", OUT_DIR / "sample.xls")


def write_ods():
    """Crée sample.ods avec 2 onglets et cellules fusionnées (odfpy)."""
    from odf.opendocument import OpenDocumentSpreadsheet
    from odf.table import CoveredTableCell, Table, TableCell, TableRow
    from odf.text import P

    doc = OpenDocumentSpreadsheet()
    # Feuille 1
    t1 = Table(name="Feuille1")
    doc.spreadsheet.addElement(t1)
    tr = TableRow()
    tc = TableCell(numbercolumnsspanned=2)
    tc.addElement(P(text="Titre fusionné"))
    tr.addElement(tc)
    t1.addElement(tr)
    def cell(s):
        c = TableCell(valuetype="string")
        c.addElement(P(text=s))
        return c

    tr = TableRow()
    tr.addElement(cell("Col A"))
    tr.addElement(cell("Col B"))
    t1.addElement(tr)
    for label, val in [("Ligne 1", "10"), ("Ligne 2", "20")]:
        tr = TableRow()
        tr.addElement(cell(label))
        tr.addElement(cell(val))
        t1.addElement(tr)
    tr = TableRow()
    tc = TableCell(numbercolumnsspanned=2)
    tc.addElement(P(text="Total"))
    tr.addElement(tc)
    t1.addElement(tr)
    # Feuille 2 (fusion verticale : Section sur 3 lignes, puis cellules couvertes)
    t2 = Table(name="Feuille2")
    doc.spreadsheet.addElement(t2)
    tr = TableRow()
    tc = TableCell(numberrowsspanned=3)
    tc.addElement(P(text="Section"))
    tr.addElement(tc)
    tr.addElement(cell("V1"))
    t2.addElement(tr)
    tr = TableRow()
    tr.addElement(CoveredTableCell())
    tr.addElement(cell("V2"))
    t2.addElement(tr)
    tr = TableRow()
    tr.addElement(CoveredTableCell())
    tr.addElement(cell("V3"))
    t2.addElement(tr)
    tr = TableRow()
    tr.addElement(cell("Fin"))
    t2.addElement(tr)
    doc.save(OUT_DIR / "sample.ods")
    print("Créé:", OUT_DIR / "sample.ods")


if __name__ == "__main__":
    write_xlsx()
    write_xls()
    write_ods()
