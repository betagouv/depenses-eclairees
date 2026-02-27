import io
import random

import pytest
from PIL import Image, ImageEnhance, ImageFilter

from docia.file_processing.processor.text_extraction import extract_text_from_image

from .utils import ASSETS_DIR, assert_similar_text


@pytest.fixture(scope="module", autouse=True)
def fix_random_seed():
    """Fix random seed for all tests in this module"""
    random.seed(42)


@pytest.mark.parametrize(
    "extension",
    [
        "png",
        "jpeg",
        "tiff",
    ],
)
def test_extract_text_from_image(extension):
    with open(ASSETS_DIR / "lettre.png", "rb") as f:
        file_content = f.read()

    # Convert to other formats if needed
    if extension != "png":
        buff = io.BytesIO()
        im = Image.open(io.BytesIO(file_content))
        im = im.convert("RGB")
        im.save(buff, format=extension)
        file_content = buff.getvalue()

    text, is_ocr = extract_text_from_image(file_content, f"file.{extension}")
    assert is_ocr
    assert_similar_text(text, 0.95)


def add_noise(image, percent):
    """Add random pixel noise"""
    pixels = image.load()
    width, height = image.size

    for _ in range(int(width * height * percent)):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        pixels[x, y] = random.randint(0, 255)

    return image


def make_image_messy(file_content, noise_level="medium"):
    """
    Apply various degradations to simulate real-world scanning conditions

    noise_level: 'light', 'medium', or 'heavy'
    """
    image = Image.open(io.BytesIO(file_content))

    if noise_level == "light":
        # Slight blur
        image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
        # Slight brightness/contrast adjustment
        image = ImageEnhance.Brightness(image).enhance(0.95)

    elif noise_level == "medium":
        # Moderate blur
        image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
        # Add some noise
        image = add_noise(image, 0.05)
        # Adjust contrast
        image = ImageEnhance.Contrast(image).enhance(0.8)

    elif noise_level == "heavy":
        # Heavy blur
        image = image.filter(ImageFilter.GaussianBlur(radius=0.75))
        # More noise
        image = add_noise(image, 0.07)
        # Darken and reduce contrast
        image = ImageEnhance.Brightness(image).enhance(0.9)
        image = ImageEnhance.Contrast(image).enhance(0.6)

    # Convert back to bytes
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def apply_jpeg_compression(file_content, quality=50):
    """Simulate poor quality scans"""
    image = Image.open(io.BytesIO(file_content))
    # Convert to RGB if needed (JPEG doesn't support transparency)
    if image.mode != "RGB":
        image = image.convert("RGB")
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=quality)
    return output.getvalue()


def add_rotation(file_content, angle=2):
    """Slight rotation (common in scanned docs)"""
    image = Image.open(io.BytesIO(file_content))
    image = image.rotate(angle, expand=True, fillcolor="white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def add_skew(file_content):
    """Perspective skew"""
    image = Image.open(io.BytesIO(file_content))
    width, height = image.size

    # Slight perspective transform
    image = image.transform(image.size, Image.PERSPECTIVE, (1, 0.05, 0, 0.02, 1, 0, 0.0001, 0.0001), Image.BICUBIC)

    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def reduce_resolution(file_content, scale=0.5):
    """Simulate low-DPI scans"""
    image = Image.open(io.BytesIO(file_content))
    new_size = (int(image.width * scale), int(image.height * scale))
    image = image.resize(new_size, Image.LANCZOS)
    image = image.resize((image.width * 2, image.height * 2), Image.NEAREST)

    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.mark.parametrize(
    "degradation,threshold",
    [
        ("blur", 0.95),
        ("noise", 0.90),
        ("heavy_noise", 0.60),
        ("compression", 0.95),
        ("rotation", 0.90),
        ("skew", 0.90),
        ("lowres", 0.90),
    ],
)
def test_extract_text_from_degraded_image(degradation, threshold):
    with open(ASSETS_DIR / "lettre.png", "rb") as f:
        file_content = f.read()

    if degradation == "blur":
        file_content = make_image_messy(file_content, "light")
    elif degradation == "noise":
        file_content = make_image_messy(file_content, "medium")
    elif degradation == "heavy_noise":
        file_content = make_image_messy(file_content, "heavy")
    elif degradation == "compression":
        file_content = apply_jpeg_compression(file_content, quality=30)
    elif degradation == "rotation":
        file_content = add_rotation(file_content, angle=1)
    elif degradation == "skew":
        file_content = add_skew(file_content)
    elif degradation == "lowres":
        file_content = reduce_resolution(file_content, scale=0.7)
    else:
        raise ValueError(f"Unknown degradation: {degradation}")

    text, is_ocr = extract_text_from_image(file_content, "file.png")

    with open(f"/tmp/test_image_{degradation}.png", "wb") as f:
        f.write(file_content)
    with open(f"/tmp/test_image_{degradation}.png.txt", "w") as f:
        f.write(text)

    assert is_ocr
    assert_similar_text(text, threshold)
