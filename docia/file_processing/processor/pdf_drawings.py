import pymupdf


def get_drawing_center(drawing):
    """
    Calcule le centre d'un dessin à partir de son rectangle.
    Args:
        drawing: Dictionnaire de dessin avec une clé 'rect'
    Returns:
        Tuple (x, y) du centre, ou None si pas de rectangle
    """
    rect = drawing.get('rect', None)
    if not rect:
        return None
    
    center_x = (rect.x0 + rect.x1) / 2
    center_y = (rect.y0 + rect.y1) / 2
    return (center_x, center_y)


def calculate_distance(center1, center2):
    """
    Calcule la distance euclidienne entre deux centres.
    Args:
        center1: Tuple (x, y) ou None
        center2: Tuple (x, y) ou None
    Returns:
        Distance en points, ou float('inf') si un centre est None
    """
    if center1 is None or center2 is None:
        return float('inf')
    
    dx = center1[0] - center2[0]
    dy = center1[1] - center2[1]
    return (dx**2 + dy**2)**0.5


def get_all_drawing_centers(drawings):
    """
    Calcule les centres de tous les dessins.
    Returns:
        Liste de tuples (x, y) ou None pour chaque dessin
    """
    centers = []
    for drawing in drawings:
        center = get_drawing_center(drawing)
        centers.append(center)
    return centers


def find_nearby_drawings(center, centers, distance_threshold, exclude_indices):
    """
    Trouve tous les indices de dessins proches d'un centre donné.
    
    Args:
        center: Tuple (x, y) du centre de référence
        centers: Liste de tous les centres
        distance_threshold: Distance maximale pour considérer comme proche
        exclude_indices: Ensemble d'indices à exclure de la recherche
    
    Returns:
        Liste d'indices de dessins proches
    """
    nearby = []
    
    if center is None:
        return nearby
    
    for i, other_center in enumerate(centers):
        if i in exclude_indices:
            continue
        
        if other_center is None:
            continue
        
        distance = calculate_distance(center, other_center)
        if distance <= distance_threshold:
            nearby.append(i)
    
    return nearby


def group_drawings_by_location(drawings, distance_threshold= 10):
    """
    Regroupe les dessins qui sont proches spatialement.
    
    Args:
        drawings: Liste de dessins (dict avec 'rect')
        distance_threshold: Distance maximale en points pour considérer deux dessins comme proches.
                          Si None, utilise automatiquement un seuil basé sur la taille moyenne
    
    Returns:
        Liste de groupes, chaque groupe étant une liste d'indices de dessins
    """
    if not drawings:
        return []
    
    # Étape 1: Calculer les centres de tous les dessins
    centers = get_all_drawing_centers(drawings)
    
    # Étape 2: Regrouper les dessins proches
    groups = []
    used = set()
    
    for i, center in enumerate(centers):
        # Ignorer si déjà utilisé ou pas de centre valide
        if i in used or center is None:
            continue
        
        # Créer un nouveau groupe avec ce dessin
        group = [i]
        used.add(i)
        
        # Trouver tous les dessins proches
        nearby_indices = find_nearby_drawings(center, centers, distance_threshold, used)
        
        # Ajouter les dessins proches au groupe
        for j in nearby_indices:
            group.append(j)
            used.add(j)
        
        groups.append(group)
    
    return groups


def cm_to_points(cm):
    """Convertit des centimètres en points"""
    return cm * 10 / 0.3528


def points_to_cm(points):
    """Convertit des points en centimètres"""
    return points * 0.3528 / 10


def is_square(rect, tolerance=2.0):
    """
    Vérifie si un rectangle est un carré (avec une tolérance en points).
    
    Args:
        rect: Rectangle PyMuPDF
        tolerance: Tolérance en points pour considérer comme carré
    
    Returns:
        bool: True si c'est un carré
    """
    if not rect:
        return False
    width = rect.width
    height = rect.height
    return abs(width - height) <= tolerance


def has_small_square_item(drawing, max_size_cm=0.5, min_size_cm=0.25):
    """
    Vérifie si un dessin contient un item rectangle carré de taille inférieure à max_size_cm.
    
    Args:
        drawing: Dictionnaire de dessin
        max_size_cm: Taille maximale en cm
    
    Returns:
        True si le dessin contient un petit carré dans ses items, False sinon
    """
    items = drawing.get('items', [])
    
    for item in items:
        # Chercher les items de type rectangle
        if item[0] == 're' and is_square(item[1]):  # Rectangle
            size_cm = points_to_cm(max(item[1].width, item[1].height))
            if size_cm < max_size_cm and size_cm > min_size_cm:
                return True
        elif item[0] == 'qu' and is_square(drawing.get('rect', None)):
            drawing_rect = drawing.get('rect', None)
            size_cm = points_to_cm(max(drawing_rect.width, drawing_rect.height))
            if size_cm < max_size_cm and size_cm > min_size_cm:
                return True
    return False


def count_segments_in_drawing(drawing):
    """
    Compte le nombre de segments (lignes) dans les items d'un dessin.
    
    Args:
        drawing: Dictionnaire de dessin
    
    Returns:
        Nombre de segments trouvés
    """
    items = drawing.get('items', [])
    count = 0
    
    for item in items:
        if not item or len(item) < 2:
            continue
        
        if item[0] == 'l':  # Ligne
            count += 1
    
    return count


def count_total_segments_in_group(drawings, group_indices):
    """
    Compte le nombre total de segments dans tous les dessins d'un groupe.
    
    Args:
        drawings: Liste de tous les dessins
        group_indices: Liste d'indices de dessins dans le groupe
    
    Returns:
        Nombre total de segments
    """
    total = 0
    for idx in group_indices:
        if idx < len(drawings):
            total += count_segments_in_drawing(drawings[idx])
    return total


def get_group_center(drawings, group_indices):
    """
    Calcule le centre d'un groupe de dessins.
    
    Args:
        drawings: Liste de tous les dessins
        group_indices: Liste d'indices de dessins dans le groupe
    
    Returns:
        Tuple (x, y) du centre, ou None si aucun centre valide
    """
    centers = []
    for idx in group_indices:
        if idx < len(drawings):
            center = get_drawing_center(drawings[idx])
            if center:
                centers.append(center)
    
    if not centers:
        return None
    
    avg_x = sum(c[0] for c in centers) / len(centers)
    avg_y = sum(c[1] for c in centers) / len(centers)
    return (avg_x, avg_y)


def deduce_checkbox_caracters_from_groups(drawings, groups):
    """
    Déduit les blocs de texte à ajouter à partir des groupes de dessins.
    
    Args:
        drawings: Liste de tous les dessins
        groups: Liste de groupes (chaque groupe est une liste d'indices)
    
    Returns:
        Liste de blocs de texte PyMuPDF
    """
    checkbox_caracters = []
    
    for group in groups:
        # Vérifier si le groupe contient un petit carré
        for idx in group:
            if idx < len(drawings) and has_small_square_item(drawings[idx]):
                # Compter les segments dans les dessins du groupe
                total_segments = count_total_segments_in_group(drawings, group)
                
                # Calculer le centre du groupe
                center = get_group_center(drawings, group)
                center = (center[0], center[1]-5) # on décale le centre vers le haut pour que la check box apparaisse avant le texte.

                # Déterminer le caractère à utiliser
                if total_segments >= 2:
                    character = '[X]'  # ☒ (case cochée)
                else:
                    character = '[ ]'  # ☐ (case non cochée)
                
                # Créer le bloc de texte
                checkbox_caracter = (character, center)
                checkbox_caracters.append(checkbox_caracter)
    
    return checkbox_caracters


def add_checkbox_drawings_in_text(page):
    # Créer une copie de la page
    new_doc = pymupdf.Document()
    new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
    new_page.show_pdf_page(new_page.rect, page.parent, page.number)

    # Répérage et récupération des check boxes
    drawings = page.get_drawings()
    groups = group_drawings_by_location(drawings)
    checkbox_caracters = deduce_checkbox_caracters_from_groups(drawings, groups)

    # Insertion des check boxes dans le texte
    font_size_pt = cm_to_points(0.3)
    for checkbox_caracter in checkbox_caracters:
        character, center = checkbox_caracter
        
        pos = pymupdf.Point(center[0], center[1] + font_size_pt / 2)
        new_page.insert_text(pos, character, fontsize=font_size_pt, 
                            color=(0, 0, 0), fontname="helv")
    
    return new_doc


def add_drawings_to_pdf(doc):
    new_doc = pymupdf.Document()

    # Ajouter les opérations sur les dessins des pages
    for i, page in enumerate(doc):
        
        temp_doc = add_checkbox_drawings_in_text(page)
        
        new_doc.insert_pdf(temp_doc, from_page=0, to_page=0)

    return new_doc

