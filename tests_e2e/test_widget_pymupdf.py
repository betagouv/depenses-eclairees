import pymupdf
import os
import django

import sys
sys.path.append(".")

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'docia.settings')
django.setup()

from django.core.files.storage import default_storage
from docia.models import Document

from docia.file_processing.processor.pdf_drawings import (
    add_checkbox_drawings_in_text,
    add_drawings_to_pdf,
    calculate_distance,
    cm_to_points,
    count_segments_in_drawing,
    count_total_segments_in_group,
    deduce_checkbox_caracters_from_groups,
    get_all_drawing_centers,
    get_drawing_center,
    get_group_center,
    group_drawings_by_location,
    has_small_square_item,
    is_square,
    points_to_cm,
    find_nearby_drawings,
)


########################################################
########################################################


def get_squares_from_pages(drawings):
    # Filtrer uniquement les carrés
    squares = []
    for i, drawing in enumerate(drawings):
        rect = drawing.get('rect', None)
        if rect and is_square(rect):
            squares.append((i, drawing, rect))

    print(f"Carrés détectés: {len(squares)}\n")
    return squares


def print_drawings_info(drawings):
    # Afficher les informations des carrés uniquement
    for idx, drawing in enumerate(drawings, 1):
        print(f"{'='*80}")
        print(f"DESSIN #{idx}")
        print(f"{'='*80}")
        
        # Type
        print(f"Type: {drawing.get('type', 'N/A')}")
        
        # Rectangle et dimensions
        rect = drawing.get('rect', None)
        print(f"Rectangle: {rect}")
        side_pt = rect.width  # C'est un carré, donc width = height
        side_cm = points_to_cm(side_pt)
        print(f"Dimensions: {side_pt:.2f} × {side_pt:.2f} points ({side_cm:.2f} × {side_cm:.2f} cm)")
        print(f"Position: X={rect.x0:.2f}, Y={rect.y0:.2f} points")
        
        # Couleur du trait
        color = drawing.get('color', None)
        if color:
            if isinstance(color, (list, tuple)) and len(color) >= 3:
                r, g, b = color[0], color[1], color[2]
                r_255 = int(r * 255) if r <= 1 else int(r)
                g_255 = int(g * 255) if g <= 1 else int(g)
                b_255 = int(b * 255) if b <= 1 else int(b)
                print(f"Couleur du trait (RGB): ({r_255}, {g_255}, {b_255}) [normalisé: ({r:.3f}, {g:.3f}, {b:.3f})]")
            else:
                print(f"Couleur du trait: {color}")
        else:
            print(f"Couleur du trait: Non spécifiée (par défaut: noir)")
        
        # Couleur de remplissage
        fill = drawing.get('fill', None)
        if fill is not None:
            if isinstance(fill, (list, tuple)) and len(fill) >= 3:
                r, g, b = fill[0], fill[1], fill[2]
                r_255 = int(r * 255) if r <= 1 else int(r)
                g_255 = int(g * 255) if g <= 1 else int(g)
                b_255 = int(b * 255) if b <= 1 else int(b)
                print(f"Remplissage (RGB): ({r_255}, {g_255}, {b_255}) [normalisé: ({r:.3f}, {g:.3f}, {b:.3f})]")
            else:
                print(f"Remplissage: {fill}")
        else:
            print(f"Remplissage: Aucun")
        
        # Largeur du trait
        width = drawing.get('width', None)
        if width:
            width_cm = points_to_cm(width)
            print(f"Largeur du trait: {width:.2f} points ({width_cm:.2f} cm)")
        
        # Items
        items = drawing.get('items', [])
        print(f"Items: {len(items)} élément(s)")
        
        # Afficher le nombre d'items, la liste des items, leurs positions et leur type
        print(f"Nombre d'items : {len(items)}")
        if items:
            print("Liste des items :")
            for j, item in enumerate(items):
                # Type de l'item (premier élément, habituellement ex: 're', 'l', 'c', ...)
                item_type = item[0] if len(item) > 0 else "Inconnu"
                
                # Position de l'item selon son type
                pos_str = "Position inconnue"
                if len(item) > 1:
                    try:
                        if item_type == 're':  # Rectangle
                            # item[1] est un Rect
                            item_rect = item[1]
                            if hasattr(item_rect, 'x0'):  # C'est un Rect
                                pos_str = f"X={item_rect.x0:.2f}, Y={item_rect.y0:.2f}, largeur={item_rect.width:.2f}, hauteur={item_rect.height:.2f}"
                            else:
                                pos_str = f"Rect: {item_rect}"
                        
                        elif item_type == 'l':  # Ligne
                            # item[1:5] = [x1, y1, x2, y2] ou item[1] et item[2] sont des Points
                            if len(item) >= 5:
                                if hasattr(item[1], 'x'):  # Points
                                    p1, p2 = item[1], item[2]
                                    pos_str = f"Ligne: ({p1.x:.2f}, {p1.y:.2f}) → ({p2.x:.2f}, {p2.y:.2f})"
                                else:  # Coordonnées directes
                                    pos_str = f"Ligne: ({item[1]:.2f}, {item[2]:.2f}) → ({item[3]:.2f}, {item[4]:.2f})"
                            else:
                                pos_str = f"Ligne (structure: {item[1:]})"
                        
                        elif item_type == 'c':  # Courbe
                            # item[1:9] = coordonnées de la courbe
                            if len(item) >= 9:
                                pos_str = f"Courbe: 4 points"
                            else:
                                pos_str = f"Courbe (structure: {item[1:]})"
                        
                        elif item_type == 'qu':  # Quadrilatère
                            # item[1:9] = coordonnées du quadrilatère
                            if len(item) >= 9:
                                pos_str = f"Quadrilatère: 4 points"
                            else:
                                pos_str = f"Quadrilatère (structure: {item[1:]})"
                        
                        else:
                            # Pour les autres types, essayer d'afficher ce qu'on peut
                            if hasattr(item[1], 'x0'):  # Rect
                                item_rect = item[1]
                                pos_str = f"X={item_rect.x0:.2f}, Y={item_rect.y0:.2f}, largeur={item_rect.width:.2f}, hauteur={item_rect.height:.2f}"
                            elif hasattr(item[1], 'x'):  # Point
                                point = item[1]
                                pos_str = f"Point: ({point.x:.2f}, {point.y:.2f})"
                            else:
                                pos_str = f"Structure: {item[1:]}"
                    except Exception as e:
                        pos_str = f"Erreur lors de l'extraction: {e}"
                
                print(f"  - Item {j} : type={item_type}, {pos_str}")
        else:
            print("Aucun item")


def save_pdf_with_squares(squares, path = "/Users/dinum-284659/dev/data/"):
    # Créer un PDF avec uniquement les carrés détectés
    if squares:
        print(f"\n{'='*80}")
        print("CRÉATION D'UN PDF AVEC LES CARRÉS DÉTECTÉS")
        print(f"{'='*80}\n")
        
        # Créer un nouveau document PDF
        new_doc = pymupdf.Document()
        
        # Obtenir les dimensions de la page originale
        original_page = pymu_doc[0]
        page_rect = original_page.rect
        
        # Créer une nouvelle page avec les mêmes dimensions
        new_page = new_doc.new_page(width=page_rect.width, height=page_rect.height)
        
        # Redessiner chaque carré sur la nouvelle page
        for idx, (drawing_idx, drawing, rect) in enumerate(squares, 1):
            print(f"  → Ajout du carré #{idx} à la position ({rect.x0:.2f}, {rect.y0:.2f})")
            
            # Créer un shape pour redessiner les items
            shape = new_page.new_shape()
            
            # Récupérer tous les items du dessin
            items = drawing.get('items', [])
            
            if items:
                # Parcourir tous les items et ne redessiner que les rectangles et lignes
                for item in items:
                    if not item or len(item) < 2:
                        continue
                    
                    item_type = item[0]
                    
                    if item_type == 'l' and len(item) == 3:  # Ligne
                        # item[1:5] = [x1, y1, x2, y2] ou item[1] et item[2] sont des Points
                        shape.draw_line(item[1], item[2])
                    
                    elif item_type == 're':  # Rectangle
                        continue
                        # item[1] est un Rect
                        if len(item) >= 2:
                            item_rect = item[1]
                            shape.draw_rect(item_rect)
                
                # Appliquer le style noir et blanc (noir, pas de remplissage)
                shape.finish(fill=None, color=[0, 0, 0], width=1.0)
            else:
                # Si pas d'items, dessiner au moins le rectangle
                shape.draw_rect(rect)
                shape.finish(fill=None, color=[0, 0, 0], width=1.0)
            
            shape.commit()
        
        # Sauvegarder le PDF
        output_path = path + "squares_only.pdf"
        new_doc.save(output_path)
        new_doc.close()
        
        print(f"\n✓ PDF créé avec {len(squares)} carré(s) : {output_path}")
        print(f"  Dimensions de la page : {page_rect.width:.2f} × {page_rect.height:.2f} points")
    else:
        print("\n⚠️  Aucun carré détecté, aucun PDF ne sera créé.")




doc = Document.objects.filter(filename="1300202585_Metassistance_AE_24_BAM_035_LOT_2_VF.pdf")
file_path = doc[0].file.name

# with default_storage.open(file_path, 'rb') as f:
#         file_content = f.read()

with open("/Users/dinum-284659/dev/data/test/checkbox_pymupdf/1512354014_EY_ATTRI1_DGAL_2023_075_VSignee.pdf", "rb") as pdf_file:
    file_content = pdf_file.read()


pymu_doc = pymupdf.Document(stream=file_content)


page = pymu_doc[0]
new_page = add_checkbox_drawings_in_text(page, save_path="/Users/dinum-284659/dev/data/")
new_doc = add_drawings_to_pdf(pymu_doc, save_path="/Users/dinum-284659/dev/data/")

drawings = page.get_drawings()
print_drawings_info(drawings)



squares = get_squares_from_pages(page.get_drawings())
print_drawings_info(squares)



# 5. Extraire le texte avec les positions (pour voir si la case est dans le texte)
text_dict = pymu_doc[0].get_text("dict")
print(f"\n5. BLOCS DE TEXTE: {len(text_dict.get('blocks', []))} trouvé(s)")
for i, block in enumerate(text_dict.get('blocks', [])):
    if block.get('type') == 0:  # Type 0 = texte
        print(f"   Bloc texte {i+1}:")
        print(f"     - Rectangle: {block.get('bbox', 'N/A')}")
        print(f"     - Lignes: {len(block.get('lines', []))}")
        # Afficher le texte
        lines_text = []
        for line in block.get('lines', []):
            for span in line.get('spans', []):
                lines_text.append(span.get('text', ''))
        text_content = ' '.join(lines_text)
        if text_content.strip():
            print(f"     - Texte: {text_content[:100]}")