import os
import base64

def get_ingredient_images():
    """Return a dictionary mapping ingredients to base64 data URI image sources loaded from the local imgs folder"""
    base_dir = os.path.dirname(__file__)
    imgs_dir = os.path.join(base_dir, "imgs")

    # Map ingredient names to local filenames
    filename_map = {
        "Leaf": "CGUuB2u - Imgur.png",
        "Sand": "FOQ1xFS - Imgur.png",
        "Water": "u6EWIJo - Imgur.png",
        "Lightning": "FvsyopO - Imgur.png",
        "Poison": "AipJ3Yt - Imgur.png",
        "Beetle": "bdFdyx0 - Imgur.png",
        "Tooth": "4jZrlLN - Imgur.png",
        "Flame": "qJNRGqq - Imgur.png",
        "Steel": "Wb606H3 - Imgur.png",
        "Scale": "nfZPsNs - Imgur.png",
        "Essence": "Q15uLvW - Imgur.png",
        "Power": "Z6cupwx - Imgur.png",
        "Shadow": "oVOhOh6 - Imgur.png",
        "Spirit": "kcLJ0Nh - Imgur.png",
        "Petal": "gtiQgMt - Imgur.png",
        "Berries": "OCp0DoE - Imgur.png",
        "Crystal": "KJvnNaG - Imgur.png",
        "Feather": "dWg2BnN - Imgur.png",
        "Acorn": "AOswOIi - Imgur.png",
        "Egg": "JeqRY8x - Imgur.png",
        "Mushroom": "lGZtYOj - Imgur.png",
        "Pepper": "nHb35IP - Imgur.png",
    }

    images: dict[str, str] = {}
    for ingredient, filename in filename_map.items():
        img_path = os.path.join(imgs_dir, filename)
        try:
            with open(img_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            images[ingredient] = f"data:image/png;base64,{b64}"
        except FileNotFoundError:
            images[ingredient] = ""
    return images