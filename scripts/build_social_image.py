"""Draw the link preview image (dashboard/og-image.png, 1200x630) shown when the site is shared.

Numbers come from the saved results, so the card stays in step with the site. Run after
build_decision_answer.py and build_static_dashboard.py, on macOS (it uses the system Helvetica):
    .venv/bin/python scripts/build_social_image.py
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'dashboard' / 'og-image.png'
FONT = '/System/Library/Fonts/HelveticaNeue.ttc'
W, H = 1200, 630


def font(size, bold=False):
    return ImageFont.truetype(FONT, size, index=1 if bold else 0)


def main():
    decision = json.loads((ROOT / 'data/processed/decision_answer.json').read_text())
    six = decision['middle_mile_check']['affordable_6_workers']
    ten = decision['middle_mile_check']['safe_10_workers']
    affordable, resilient = decision['actions']['affordable_base_case'], decision['actions']['lowest_risk_tested']

    image = Image.new('RGB', (W, H))
    draw = ImageDraw.Draw(image, 'RGBA')
    for x in range(W):  # the site's navy to teal hero gradient
        t = x / W
        draw.line([(x, 0), (x, H)], fill=(int(23 - 10 * t), int(50 + 41 * t), int(77 + 17 * t)))
    draw.rounded_rectangle([64, 60, 112, 108], 12, fill=(255, 255, 255))
    draw.text((88, 84), 'W', font=font(28, True), fill=(23, 50, 77), anchor='mm')
    draw.text((128, 64), 'Workforce Capacity Planner', font=font(28, True), fill='white')
    draw.text((128, 98), 'FULFILLMENT OPERATIONS ANALYTICS', font=font(15), fill=(127, 211, 204))
    draw.text((64, 170), 'How many warehouse workers do three', font=font(50, True), fill='white')
    draw.text((64, 230), 'Midwest sites need, and what does the', font=font(50, True), fill='white')
    draw.text((64, 290), 'choice cost once parcels hit the road?', font=font(50, True), fill='white')

    tiles = [(f'{six["orders"]:,}', 'real 2023 orders replayed'),
             (f'{affordable["stress_cases_passed"]} vs {resilient["stress_cases_passed"]}', 'stress tests passed, 6 vs 10 workers'),
             (f'{six["late_with_truck_delays"]:,} vs {ten["late_with_truck_delays"]}', 'late parcels, 6 vs 10 workers')]
    for i, (value, label) in enumerate(tiles):
        x = 64 + i * 364
        draw.rounded_rectangle([x, 400, x + 340, 530], 16, fill=(255, 255, 255, 22), outline=(255, 255, 255, 50))
        draw.text((x + 24, 420), value, font=font(44, True), fill='white')
        draw.text((x + 24, 482), label, font=font(19), fill=(185, 205, 223))
    draw.text((64, 566), 'Forecast demand  ·  Plan capacity  ·  Ship parcels      Tri Vi  ·  github.com/vmtri15',
              font=font(19), fill=(185, 205, 223))
    image.save(OUTPUT, optimize=True)
    print(f'Wrote {OUTPUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
