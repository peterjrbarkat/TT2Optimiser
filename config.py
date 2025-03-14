def get_ingredient_images():
    """Return a dictionary mapping ingredients to their image URLs"""
    return {
        "Leaf": "https://i.imgur.com/CGUuB2u.png",
        "Sand": "https://i.imgur.com/FOQ1xFS.png",
        "Water": "https://i.imgur.com/u6EWIJo.png",
        "Lightning": "https://i.imgur.com/FvsyopO.png",
        "Poison": "https://i.imgur.com/AipJ3Yt.png",
        "Beetle": "https://i.imgur.com/bdFdyx0.png",
        "Tooth": "https://i.imgur.com/4jZrlLN.png",
        "Flame": "https://i.imgur.com/qJNRGqq.png",
        "Steel": "https://i.imgur.com/Wb606H3.png",
        "Scale": "https://i.imgur.com/nfZPsNs.png",
        "Essence": "https://i.imgur.com/Q15uLvW.png",
        "Power": "https://i.imgur.com/Z6cupwx.png",
        "Shadow": "https://i.imgur.com/oVOhOh6.png",
        "Spirit": "https://i.imgur.com/kcLJ0Nh.png",
        "Petal": "https://i.imgur.com/gtiQgMt.png",
        "Berries": "https://i.imgur.com/OCp0DoE.png",
        "Crystal": "https://i.imgur.com/KJvnNaG.png",
        "Feather": "https://i.imgur.com/dWg2BnN.png",
        "Acorn": "https://i.imgur.com/AOswOIi.png",
        "Egg": "https://i.imgur.com/JeqRY8x.png",
        "Mushroom": "https://i.imgur.com/lGZtYOj.png",
        "Pepper": "https://i.imgur.com/nHb35IP.png"
    }

def get_default_importance_scores():
    """Return default importance scores for different loot types"""
    return {
        "Currency": 100,
        "Shards": 1,
        "Perks": 1,
        "Raid Cards": 1,
        "Common Equipment": 1,
        "Rare Equipment": 1,
        "Event Equipment": 1,
        "Dust": 1,
        "Skill Points": 1,
        "Pet Eggs": 1,
        "Clan Eggs": 1,
        "Wildcards": 1,
        "Clan Scrolls": 1,
        "Hero Weapons": 1
    }