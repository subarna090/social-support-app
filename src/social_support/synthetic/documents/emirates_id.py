"""Mock identity card PNG (research R7). Plain layout: no emblems, no official titles or design."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from social_support.synthetic.documents.common import MARKING, RenderedDocument

SIZE = (1012, 638)  # ID-1 card ratio
BACKGROUND = (232, 240, 238)
INK = (30, 40, 50)
RED = (200, 20, 20)
FIELDS = (
    ("full_name", "Name"),
    ("emirates_id", "ID Number"),
    ("nationality", "Nationality"),
    ("date_of_birth", "Date of Birth"),
    ("sex", "Sex"),
    ("expiry_date", "Expiry Date"),
)


def render_emirates_id(shown: dict, path: Path) -> RenderedDocument:
    image = Image.new("RGB", SIZE, BACKGROUND)
    draw = ImageDraw.Draw(image)
    title, label, value, small = (ImageFont.load_default(size=n) for n in (40, 20, 30, 18))

    draw.text((40, 28), "MOCK RESIDENT IDENTITY CARD", font=title, fill=INK)
    draw.text(
        (40, 80),
        "Specimen for software testing. Not an official document.",
        font=small,
        fill=(90, 90, 90),
    )

    # Grey silhouette instead of a photo.
    draw.rectangle((40, 130, 260, 430), fill=(205, 210, 212), outline=(150, 150, 150), width=2)
    draw.ellipse((105, 165, 195, 255), fill=(150, 155, 158))
    draw.ellipse((75, 270, 225, 420), fill=(150, 155, 158))

    boxes: dict[str, tuple[int, int, int, int]] = {}
    y = 130
    for key, caption in FIELDS:
        draw.text((300, y), caption, font=label, fill=(90, 90, 90))
        text = str(shown[key])
        position = (300, y + 22)
        draw.text(position, text, font=value, fill=INK)
        left, top, right, bottom = draw.textbbox(position, text, font=value)
        boxes[key] = (int(left), int(top), int(right), int(bottom))
        y += 66

    # Red synthetic banner across the bottom (FR-017).
    draw.rectangle((0, SIZE[1] - 60, SIZE[0], SIZE[1]), fill=RED)
    # Pillow's bundled font has no en dash glyph, so the image uses a plain hyphen.
    banner = MARKING.replace("–", "-")
    draw.text((SIZE[0] // 2, SIZE[1] - 30), banner, font=label, fill="white", anchor="mm")
    draw.text((SIZE[0] - 40, 40), "SYNTHETIC", font=label, fill=RED, anchor="ra")

    image.save(path, format="PNG")
    return RenderedDocument(path, shown, field_boxes=boxes)
