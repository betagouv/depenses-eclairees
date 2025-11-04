#!/bin/sh

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check if libreoffice command exists, otherwise find it
if command -v libreoffice >/dev/null 2>&1; then
    LIBREOFFICE="libreoffice"
elif [ -f "/Applications/LibreOffice.app/Contents/MacOS/soffice" ]; then
    LIBREOFFICE="/Applications/LibreOffice.app/Contents/MacOS/soffice"
elif [ -f "/usr/bin/libreoffice" ]; then
    LIBREOFFICE="/usr/bin/libreoffice"
else
    echo "Error: LibreOffice not found!"
    exit 1
fi

# Generate document in different formats
for format in pdf docx doc odt png; do
    "$LIBREOFFICE" --headless --convert-to "$format" --outdir /tmp/ "$SCRIPT_DIR/lettre.md"
    cp /tmp/lettre.$format "$SCRIPT_DIR/"
done

# Generate pdf ocr
"$LIBREOFFICE" --headless --convert-to "pdf" --outdir /tmp/ "$SCRIPT_DIR/lettre.png"
cp /tmp/lettre.pdf "$SCRIPT_DIR/lettre-orc.pdf"
