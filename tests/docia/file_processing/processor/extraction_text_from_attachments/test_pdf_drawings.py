import pymupdf

from docia.file_processing.processor.pdf_drawings import (
    add_checkbox_drawings_in_text,
    add_drawings_to_pdf,
    calculate_distance,
    cm_to_points,
    count_segments_in_drawing,
    count_total_segments_in_group,
    deduce_checkbox_caracters_from_groups,
    find_nearby_drawings,
    get_all_drawing_centers,
    get_drawing_center,
    get_group_center,
    group_drawings_by_location,
    has_small_square_item,
    is_square,
    points_to_cm,
)

from .utils import ASSETS_DIR


def test_get_drawing_center():
    """Test que get_drawing_center calcule correctement le centre d'un rectangle."""
    rect = pymupdf.Rect(10, 20, 30, 40)
    drawing = {"rect": rect}
    center = get_drawing_center(drawing)
    assert center == (20.0, 30.0)  # (x0+x1)/2, (y0+y1)/2

    # Test sans rectangle
    drawing = {}
    center = get_drawing_center(drawing)
    assert center is None

    # Test avec rect None
    drawing = {"rect": None}
    center = get_drawing_center(drawing)
    assert center is None


def test_calculate_distance():
    """Test le calcul de distance entre deux points."""
    # Distance normale
    center1 = (0, 0)
    center2 = (3, 4)
    distance = calculate_distance(center1, center2)
    assert distance == 5.0  # Distance euclidienne: sqrt(3² + 4²) = 5

    # Même point
    center1 = (10, 20)
    center2 = (10, 20)
    distance = calculate_distance(center1, center2)
    assert distance == 0.0

    # Avec None
    center1 = (10, 20)
    center2 = None
    distance = calculate_distance(center1, center2)
    assert distance == float("inf")

    # Les deux None
    distance = calculate_distance(None, None)
    assert distance == float("inf")


def test_get_all_drawing_centers():
    """Test que get_all_drawing_centers calcule tous les centres."""
    rect1 = pymupdf.Rect(0, 0, 10, 10)
    rect2 = pymupdf.Rect(20, 20, 30, 30)
    drawings = [
        {"rect": rect1},
        {"rect": rect2},
    ]
    centers = get_all_drawing_centers(drawings)
    assert centers == [(5.0, 5.0), (25.0, 25.0)]

    # Test avec dessin sans rectangle
    rect1 = pymupdf.Rect(0, 0, 10, 10)
    drawings = [
        {"rect": rect1},
        {},  # Pas de rectangle
    ]
    centers = get_all_drawing_centers(drawings)
    assert centers == [(5.0, 5.0), None]


def test_find_nearby_drawings():
    """Test que find_nearby_drawings trouve les dessins proches."""
    center = (10, 10)
    centers = [(10, 10), (12, 12), (50, 50), (11, 11)]
    distance_threshold = 5
    exclude_indices = set()
    nearby = find_nearby_drawings(center, centers, distance_threshold, exclude_indices)
    # Les indices 0 (même point, distance 0), 1 (distance ~2.83), 3 (distance ~1.41) sont proches
    assert 0 in nearby  # Même point
    assert 1 in nearby  # Distance ~2.83
    assert 3 in nearby  # Distance ~1.41
    assert 2 not in nearby  # Trop loin (distance ~56.57)

    # Test avec exclusion d'indices
    center = (10, 10)
    centers = [(10, 10), (12, 12), (11, 11)]
    distance_threshold = 5
    exclude_indices = {1}
    nearby = find_nearby_drawings(center, centers, distance_threshold, exclude_indices)
    assert 1 not in nearby  # Exclu
    assert 0 in nearby  # Même point
    assert 2 in nearby  # Proche

    # Test avec center None
    nearby = find_nearby_drawings(None, [(10, 10), (20, 20)], 5, set())
    assert nearby == []


def test_group_drawings_by_location():
    """Test que group_drawings_by_location regroupe les dessins proches."""
    # Liste vide
    groups = group_drawings_by_location([])
    assert groups == []

    # Un seul dessin
    rect = pymupdf.Rect(10, 10, 20, 20)
    drawings = [{"rect": rect}]
    groups = group_drawings_by_location(drawings)
    assert len(groups) == 1
    assert groups[0] == [0]

    # Dessins proches
    rect1 = pymupdf.Rect(10, 10, 20, 20)
    rect2 = pymupdf.Rect(12, 12, 22, 22)  # Proche de rect1
    rect3 = pymupdf.Rect(100, 100, 110, 110)  # Loin
    drawings = [
        {"rect": rect1},
        {"rect": rect2},
        {"rect": rect3},
    ]
    groups = group_drawings_by_location(drawings, distance_threshold=5)
    # rect1 et rect2 devraient être dans le même groupe
    assert len(groups) == 2
    assert any(0 in group and 1 in group for group in groups)
    assert any(2 in group for group in groups)


def test_cm_to_points():
    """Test la conversion de centimètres en points."""
    cm = 1.0
    points = cm_to_points(cm)
    # 1 cm = 28.346 points (approximativement)
    assert abs(points - 28.346) < 0.1


def test_points_to_cm():
    """Test la conversion de points en centimètres."""
    points = 28.346
    cm = points_to_cm(points)
    # Devrait être proche de 1 cm
    assert abs(cm - 1.0) < 0.01

    # Test conversion aller-retour
    original_cm = 2.5
    points = cm_to_points(original_cm)
    back_to_cm = points_to_cm(points)
    assert abs(back_to_cm - original_cm) < 0.001


def test_is_square():
    """Test qu'un rectangle est reconnu comme carré."""
    # Carré parfait
    rect = pymupdf.Rect(0, 0, 10, 10)
    assert is_square(rect) is True

    # Rectangle presque carré avec tolérance
    rect = pymupdf.Rect(0, 0, 10, 11.5)  # Différence de 1.5
    assert is_square(rect, tolerance=2.0) is True
    assert is_square(rect, tolerance=1.0) is False

    # Rectangle non carré
    rect = pymupdf.Rect(0, 0, 10, 20)
    assert is_square(rect) is False

    # None
    assert is_square(None) is False


def test_has_small_square_item():
    """Test la détection d'un petit carré dans un dessin."""
    # Petit carré dans un rectangle
    size_pt = cm_to_points(0.3)
    rect = pymupdf.Rect(0, 0, size_pt, size_pt)
    item = ("re", rect)
    drawing = {"items": [item]}
    assert has_small_square_item(drawing, max_size_cm=0.5, min_size_cm=0.25) is True

    # Carré trop grand
    size_pt = cm_to_points(1.0)  # 1 cm, trop grand
    rect = pymupdf.Rect(0, 0, size_pt, size_pt)
    item = ("re", rect)
    drawing = {"items": [item]}
    assert has_small_square_item(drawing, max_size_cm=0.5, min_size_cm=0.25) is False

    # Carré trop petit
    size_pt = cm_to_points(0.1)  # 0.1 cm, trop petit
    rect = pymupdf.Rect(0, 0, size_pt, size_pt)
    item = ("re", rect)
    drawing = {"items": [item]}
    assert has_small_square_item(drawing, max_size_cm=0.5, min_size_cm=0.25) is False

    # Pas d'items
    drawing = {"items": []}
    assert has_small_square_item(drawing) is False

    # Quadrilatère
    size_pt = cm_to_points(0.3)
    rect = pymupdf.Rect(0, 0, size_pt, size_pt)
    item = ("qu", None)  # Le quad n'est pas utilisé, on utilise drawing.rect
    drawing = {"items": [item], "rect": rect}
    assert has_small_square_item(drawing, max_size_cm=0.5, min_size_cm=0.25) is True


def test_count_segments_in_drawing():
    """Test le comptage de segments dans un dessin."""
    # Dessin avec lignes
    item1 = ("l", pymupdf.Point(0, 0), pymupdf.Point(10, 10))
    item2 = ("re", pymupdf.Rect(0, 0, 10, 10))
    item3 = ("l", pymupdf.Point(20, 20), pymupdf.Point(30, 30))
    drawing = {"items": [item1, item2, item3]}
    count = count_segments_in_drawing(drawing)
    assert count == 2  # Deux lignes

    # Dessin sans lignes
    item = ("re", pymupdf.Rect(0, 0, 10, 10))
    drawing = {"items": [item]}
    count = count_segments_in_drawing(drawing)
    assert count == 0


def test_count_total_segments_in_group():
    """Test le comptage total de segments dans un groupe."""
    item1 = ("l", pymupdf.Point(0, 0), pymupdf.Point(10, 10))
    item2 = ("l", pymupdf.Point(20, 20), pymupdf.Point(30, 30))
    drawing1 = {"items": [item1]}
    drawing2 = {"items": [item2]}
    drawings = [drawing1, drawing2]
    group_indices = [0, 1]
    total = count_total_segments_in_group(drawings, group_indices)
    assert total == 2


def test_get_group_center():
    """Test le calcul du centre d'un groupe de dessins."""
    rect1 = pymupdf.Rect(0, 0, 10, 10)  # Centre: (5, 5)
    rect2 = pymupdf.Rect(20, 20, 30, 30)  # Centre: (25, 25)
    drawings = [
        {"rect": rect1},
        {"rect": rect2},
    ]
    group_indices = [0, 1]
    center = get_group_center(drawings, group_indices)
    # Centre moyen: ((5+25)/2, (5+25)/2) = (15, 15)
    assert center == (15.0, 15.0)

    # Groupe vide
    drawings = []
    group_indices = []
    center = get_group_center(drawings, group_indices)
    assert center is None


def test_deduce_checkbox_caracters_from_groups():
    """Test la déduction des checkboxes à partir des groupes."""
    # Checkbox cochée (>= 2 segments)
    size_pt = cm_to_points(0.3)
    rect = pymupdf.Rect(0, 0, size_pt, size_pt)
    item_rect = ("re", rect)
    item_line1 = ("l", pymupdf.Point(0, 0), pymupdf.Point(10, 10))
    item_line2 = ("l", pymupdf.Point(10, 0), pymupdf.Point(0, 10))
    drawing = {
        "items": [item_rect, item_line1, item_line2],
        "rect": rect,
    }
    drawings = [drawing]
    groups = [[0]]
    checkbox_caracters = deduce_checkbox_caracters_from_groups(drawings, groups)
    assert len(checkbox_caracters) == 1
    character, center = checkbox_caracters[0]
    assert character == "[X]"  # Coché car >= 2 segments

    # Checkbox non cochée (< 2 segments)
    size_pt = cm_to_points(0.3)
    rect = pymupdf.Rect(0, 0, size_pt, size_pt)
    item_rect = ("re", rect)
    drawing = {
        "items": [item_rect],
        "rect": rect,
    }
    drawings = [drawing]
    groups = [[0]]
    checkbox_caracters = deduce_checkbox_caracters_from_groups(drawings, groups)
    assert len(checkbox_caracters) == 1
    character, center = checkbox_caracters[0]
    assert character == "[ ]"  # Non cochée car < 2 segments

    # Pas de petit carré
    rect = pymupdf.Rect(0, 0, 100, 100)  # Trop grand
    drawing = {"items": [("re", rect)], "rect": rect}
    drawings = [drawing]
    groups = [[0]]
    checkbox_caracters = deduce_checkbox_caracters_from_groups(drawings, groups)
    assert len(checkbox_caracters) == 0


def test_add_checkbox_drawings_in_text():
    """Test l'ajout de checkboxes dans une page."""
    # Créer un document PDF simple
    doc = pymupdf.Document()
    page = doc.new_page(width=200, height=200)
    page.insert_text((50, 50), "Test", fontsize=12)

    # Créer un dessin avec un petit carré
    size_pt = cm_to_points(0.3)
    rect = pymupdf.Rect(100, 100, 100 + size_pt, 100 + size_pt)
    shape = page.new_shape()
    shape.draw_rect(rect)
    shape.finish(fill=None, color=(0, 0, 0), width=1.0)
    shape.commit()

    # Appeler la fonction
    new_doc = add_checkbox_drawings_in_text(page)
    assert new_doc is not None
    assert len(new_doc) == 1
    new_doc.close()
    doc.close()


def test_add_drawings_to_pdf():
    """Test l'ajout de dessins à un document PDF complet."""
    # Document avec plusieurs pages
    doc = pymupdf.Document()
    page1 = doc.new_page(width=200, height=200)
    page1.insert_text((50, 50), "Page 1", fontsize=12)
    page2 = doc.new_page(width=200, height=200)
    page2.insert_text((50, 50), "Page 2", fontsize=12)
    new_doc = add_drawings_to_pdf(doc)
    assert new_doc is not None
    assert len(new_doc) == 2  # Même nombre de pages
    new_doc.close()
    doc.close()

    # Document vide
    doc = pymupdf.Document()
    new_doc = add_drawings_to_pdf(doc)
    assert new_doc is not None
    assert len(new_doc) == 0
    new_doc.close()
    doc.close()


def test_add_checkbox_drawings_in_text_from_pdf():
    """Test l'ajout de checkboxes dans le texte à partir d'un PDF réel."""
    # Charger le PDF checkbox.pdf
    pdf_path = ASSETS_DIR / "checkbox.pdf"
    doc = pymupdf.Document(pdf_path)
    doc_with_drawings = add_drawings_to_pdf(doc)

    new_text = doc_with_drawings[0].get_text(sort=True)
    has_checkbox = "[X]     Le signataire" in new_text and "[ ]           m’engage sur" in new_text

    assert has_checkbox

    doc_with_drawings.close()
    doc.close()
