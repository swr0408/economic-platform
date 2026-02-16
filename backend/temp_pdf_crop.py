"""Temp: Crop Chart 18 and Chart 20 from NAB PDF as images"""
import pdfplumber
from PIL import Image
import sys
sys.stdout.reconfigure(encoding='utf-8')

pdf_path = 'data/pdf/australia/NAB-Monthly-Business-Survey-August-2025.pdf'
output_dir = 'data/cache/australia/inflation'

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[3]  # Page 4 (0-indexed)

    # Convert page to high-res image (3x scale for quality)
    page_image = page.to_image(resolution=200)

    # Scale factor: 200/72 = 2.778
    scale = 200 / 72

    # Chart 18: Cost Growth (title at y0=253.5, image at y0=263.8 to y1=413.3)
    # Include title: from y0=250 to y1=417
    chart18_bbox = (
        int(42 * scale),    # x0 - left margin
        int(250 * scale),   # y0 - include title
        int(295 * scale),   # x1 - right edge of chart
        int(417 * scale),   # y1 - bottom of chart
    )

    # Chart 20: Output Price Growth (title at y0=425.1, image at y0=435.3 to y1=589.3)
    # Include title: from y0=422 to y1=593
    chart20_bbox = (
        int(42 * scale),    # x0
        int(422 * scale),   # y0 - include title
        int(295 * scale),   # x1
        int(593 * scale),   # y1
    )

    # Get the PIL image
    pil_image = page_image.original

    # Crop Chart 18
    chart18_img = pil_image.crop(chart18_bbox)
    chart18_path = f'{output_dir}/nab_chart18_cost_growth.png'
    chart18_img.save(chart18_path)
    print(f'Chart 18 saved: {chart18_path} ({chart18_img.size})')

    # Crop Chart 20
    chart20_img = pil_image.crop(chart20_bbox)
    chart20_path = f'{output_dir}/nab_chart20_output_price_growth.png'
    chart20_img.save(chart20_path)
    print(f'Chart 20 saved: {chart20_path} ({chart20_img.size})')

    print('Done!')
