"""Avatars: who runs on your screen, and who comes round to dance.

Every avatar is the same drawn capybara with its own name, fur colour, jacket colour and headwear. Pick one of the
ready-made friends below, then change anything you like. The one on screen also rides the animals (see rides.py), and
the friend can ride along behind.
"""
from __future__ import annotations

HEADWEAR = {"": "Nothing", "bandana": "Bandana", "bow": "Bow", "flower": "Flower", "cap": "Cap", "crown": "Crown"}

PRESETS = {
    "primo": {"name": "Primo", "fur": "#C98A50", "hoodie": "#1F2A5A", "acc": "", "acc_color": "#D62839",
              "about": "The Capytech mascot"},
    "jeo": {"name": "Jeo OngBack", "fur": "#E3B273", "hoodie": "#12857E", "acc": "bandana", "acc_color": "#D62839",
            "about": "Primo's best friend and dance rival"},
    "geelee": {"name": "Geelee", "fur": "#D9A27A", "hoodie": "#F06292", "acc": "bow", "acc_color": "#7E57C2",
               "about": "Sweet, quick and always first on the dance floor"},
    "koko": {"name": "Koko", "fur": "#7A4E2D", "hoodie": "#E8762B", "acc": "cap", "acc_color": "#1E6FD9",
             "about": "Chocolate-brown skater with a blue cap"},
    "luna": {"name": "Luna", "fur": "#A39A93", "hoodie": "#5C6BC0", "acc": "flower", "acc_color": "#F48FB1",
             "about": "Calm night owl with a flower behind her ear"},
    "tito": {"name": "Tito", "fur": "#E0B060", "hoodie": "#2F9E44", "acc": "crown", "acc_color": "#F2C230",
             "about": "The golden king of the capybaras"},
}

# settings keys: the avatar on screen uses the old "color" (jacket) and "pet_name" keys, the friend "friend_color"
# and "friend_name", so older settings files keep working
KEYS = {
    "main": {"preset": "avatar", "name": "pet_name", "fur": "avatar_fur", "hoodie": "color", "acc": "avatar_acc",
             "acc_color": "avatar_acc_color"},
    "friend": {"preset": "friend_avatar", "name": "friend_name", "fur": "friend_fur", "hoodie": "friend_color",
               "acc": "friend_acc", "acc_color": "friend_acc_color"},
}


def get(settings: dict, who: str = "main") -> dict:
    """{'preset', 'name', 'fur', 'hoodie', 'acc', 'acc_color'} of the avatar on screen (main) or the friend."""
    base = PRESETS["primo" if who == "main" else "jeo"]
    out = {}
    for field, key in KEYS[who].items():
        default = ("primo" if who == "main" else "jeo") if field == "preset" else base[field]
        val = settings.get(key)
        out[field] = default if val in (None, "") and field != "acc" else (val if val is not None else default)
    return out


def put(settings: dict, who: str, av: dict) -> None:
    for field, key in KEYS[who].items():
        if field in av:
            settings[key] = av[field]


def preset(key: str) -> dict:
    p = PRESETS.get(key) or PRESETS["primo"]
    return {"preset": key, **{k: p[k] for k in ("name", "fur", "hoodie", "acc", "acc_color")}}


def look(av: dict) -> dict:
    """What characters.set_avatars wants."""
    return {"fur": av["fur"], "acc": av["acc"], "acc_color": av["acc_color"]}
