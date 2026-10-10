"""Generate Labelizer4x6 icon assets for the Windows PyInstaller build."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent

def app_icon():
    scale = 3
    im = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((15, 15, 497, 497), radius=105,
                        fill=(103, 49, 163, 255), outline=(190, 136, 252, 255), width=10)
    d.rounded_rectangle((126, 95, 389, 425), radius=24, fill=(252, 249, 255))
    d.polygon([(323, 95), (389, 161), (323, 161)], fill=(215, 196, 241))
    d.line([(323, 95), (323, 161), (389, 161)], fill=(128, 70, 191), width=7)
    d.rounded_rectangle((158, 211, 359, 320), radius=12, fill=(240, 225, 254))
    x = 173
    for width in (5, 3, 8, 4, 3, 9, 5, 2, 7, 4, 9, 3, 5, 6, 3, 7, 4, 5, 8, 3, 5):
        d.rectangle((x, 224, x + width, 307), fill=(79, 32, 130))
        x += width + 3
    d.line([(83, 173), (83, 117), (137, 117)], fill=(241, 220, 255), width=13)
    d.line([(429, 338), (429, 396), (375, 396)], fill=(241, 220, 255), width=13)
    im.save(ROOT / "labelizer.ico", sizes=[(16, 16), (24, 24), (32, 32),
            (48, 48), (64, 64), (128, 128), (256, 256)])

def upload_icon():
    image = Image.new("RGBA", (144, 144), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    purple = (184, 128, 244, 255)
    d.line([(34, 10), (81, 10), (111, 40), (111, 130), (34, 130), (34, 10)],
           fill=purple, width=9, joint="curve")
    d.line([(81, 10), (81, 40), (111, 40)], fill=purple, width=9, joint="curve")
    d.line([(72, 105), (72, 58)], fill=purple, width=9)
    d.line([(52, 78), (72, 58), (92, 78)], fill=purple, width=9, joint="curve")
    image.resize((36, 36), Image.Resampling.LANCZOS).save(ROOT / "drop_pdf_icon.png")

def checked_icon():
    image = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    d.line([(10, 25), (20, 34), (38, 12)], fill=(255, 255, 255, 255), width=6, joint="curve")
    image.resize((16, 16), Image.Resampling.LANCZOS).save(ROOT / "checkbox_checked.png")

if __name__ == "__main__":
    app_icon()
    upload_icon()
    checked_icon()
    print("Labelizer4x6 artwork generated.")
