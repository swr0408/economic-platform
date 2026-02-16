"""Temp: Analyze NAB PDF page 4 layout"""
import pdfplumber
import sys
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = 'data/pdf/australia/NAB-Monthly-Business-Survey-August-2025.pdf'
with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[3]  # Page 4 (0-indexed)
    print(f'Page size: width={page.width}, height={page.height}')
    print()

    # Extract all text with positions
    words = page.extract_words()
    for w in words:
        safe = w['text'].encode('utf-8', errors='replace').decode('utf-8')
        x0 = w["x0"]
        top = w["top"]
        x1 = w["x1"]
        bottom = w["bottom"]
        print(f'  x0={x0:.1f} y0={top:.1f} x1={x1:.1f} y1={bottom:.1f} text={safe}')

    print()
    print("=== Images ===")
    images = page.images
    for img in images:
        print(f'  x0={img["x0"]:.1f} y0={img["top"]:.1f} x1={img["x1"]:.1f} y1={img["bottom"]:.1f} w={img["width"]} h={img["height"]}')
