"""3D avatars: Primo and friends built from real 3D parts, lit and drawn by a small built-in renderer.

No 3D library or graphics card is needed: every part (head, snout, ears, hoodie, shoes, hat…) is a smooth
3D shape made of small faces, turned towards the camera, lit by a soft light and painted back to front with
QPainter. That keeps CapyRunner small and it works the same on Windows, macOS and Linux.

A look is a plain dict (see DEFAULT_LOOK): every part has a style and a colour, so the Avatar Studio can
change one part at a time. Poses: idle, run, wave, talk, jump, sleep.
"""
from __future__ import annotations

import math
import os
from functools import lru_cache

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF

# --------------------------------------------------------------------------- #
# the look: every part, its style and its colour
# --------------------------------------------------------------------------- #
TOPS = {"hoodie": "Hoodie", "tee": "T-shirt", "vest": "Vest", "jacket": "Jacket (open)", "none": "Nothing"}
BOTTOMS = {"shorts": "Shorts", "pants": "Long pants", "skirt": "Skirt", "none": "Nothing"}
SHOES = {"sneakers": "Sneakers", "boots": "Boots", "sandals": "Sandals", "none": "Bare paws"}
HATS = {"": "Nothing", "cap": "Cap", "beanie": "Beanie", "crown": "Crown", "bandana": "Bandana", "bow": "Bow",
        "flower": "Flower", "tophat": "Top hat", "headphones": "Headphones", "party": "Party hat"}
GLASSES = {"": "Nothing", "round": "Round glasses", "shades": "Sunglasses", "star": "Star shades"}
NECK = {"": "Nothing", "scarf": "Scarf", "bowtie": "Bow tie", "tie": "Necktie", "chain": "Gold chain"}
EXTRAS = {"": "Nothing", "backpack": "Backpack", "cape": "Cape", "wings": "Little wings"}
EYES = {"round": "Round", "happy": "Happy (closed arcs)", "sparkle": "Sparkly", "sleepy": "Sleepy"}
BODIES = {"cartoon": "Cartoon (cute, in clothes)", "real": "Real capybara (on four legs)",
          "hero": "Real capybara standing (warriors)"}
COSTUMES = {"": "Nothing", "lapulapu": "Lapu-Lapu (Mactan warrior)", "samurai": "Samurai armour", "shogun": "Shogun armour",
            "wrap": "Woven tribal wrap"}
WEAPONS = {"": "Nothing", "kampilan": "Kampilan", "katana": "Katana"}
MOODS = {"neutral": "😌 Calm", "happy": "😊 Happy", "excited": "🤩 Excited", "love": "🥰 In love", "sad": "😢 Sad",
         "angry": "😠 Angry", "brave": "⚔ Brave", "surprised": "😮 Surprised", "sleepy": "😴 Sleepy"}

# what each mood does to the face: eyes, eyebrows, mouth, ears (+ up / - back), cheeks, head tilt, effect
FACE = {
    "neutral": {"eye": "open", "brow": "", "mouth": "smile", "ears": 0.0, "blush": 1.0, "tilt": 0.0, "fx": ""},
    "happy": {"eye": "arc", "brow": "", "mouth": "grin", "ears": 0.1, "blush": 1.3, "tilt": -0.05, "fx": ""},
    "excited": {"eye": "sparkle", "brow": "up", "mouth": "grin", "ears": 0.25, "blush": 1.3, "tilt": -0.1,
                "fx": "sparkles"},
    "love": {"eye": "arc", "brow": "", "mouth": "smile", "ears": 0.05, "blush": 2.0, "tilt": 0.1, "fx": "hearts"},
    "sad": {"eye": "half", "brow": "sad", "mouth": "frown", "ears": -0.55, "blush": 0.6, "tilt": 0.2, "fx": "tear"},
    "angry": {"eye": "open", "brow": "angry", "mouth": "frown", "ears": -0.4, "blush": 0.0, "tilt": -0.05,
              "fx": "anger"},
    "brave": {"eye": "open", "brow": "brave", "mouth": "flat", "ears": 0.1, "blush": 0.0, "tilt": -0.12, "fx": ""},
    "surprised": {"eye": "wide", "brow": "up", "mouth": "o", "ears": 0.35, "blush": 0.8, "tilt": -0.12,
                  "fx": "shock"},
    "sleepy": {"eye": "half", "brow": "", "mouth": "smile", "ears": -0.25, "blush": 1.0, "tilt": 0.12, "fx": ""},
}

DEFAULT_LOOK = {
    "body": "cartoon", "mood": "happy", "costume": "", "weapon": "", "costume_color": "#A3342B",
    "fur": "#C98A50", "muzzle": "#B47740", "eye_color": "#1E1410", "eyes": "round", "blush": True,
    "head": 1.0, "chubby": 1.0, "ears": 1.0, "height": 1.0,
    "top": "hoodie", "top_color": "#1F2A5A", "top_trim": "#F2F2F2",
    "bottom": "shorts", "bottom_color": "#3A3F4B",
    "shoes": "sneakers", "shoes_color": "#E8EDF2",
    "hat": "", "hat_color": "#D62839",
    "glasses": "", "glasses_color": "#222222",
    "neck": "", "neck_color": "#D62839",
    "extra": "", "extra_color": "#E8762B",
}

# ready-made looks (the same friends as the 2D gallery, dressed in 3D)
PRESETS = {
    "primo": {"fur": "#C98A50", "muzzle": "#B47740", "top": "hoodie", "top_color": "#1F2A5A",
              "bottom": "shorts", "bottom_color": "#3A3F4B", "shoes": "sneakers", "shoes_color": "#E8EDF2",
              "hat": "", "glasses": "", "neck": "", "extra": "backpack", "extra_color": "#E8762B"},
    "jeo": {"fur": "#E3B273", "muzzle": "#CF9A5C", "top": "hoodie", "top_color": "#12857E",
            "bottom": "pants", "bottom_color": "#2E3440", "shoes": "sneakers", "shoes_color": "#D62839",
            "hat": "bandana", "hat_color": "#D62839", "glasses": "", "neck": "chain", "neck_color": "#F2C230",
            "extra": ""},
    "geelee": {"fur": "#D9A27A", "muzzle": "#C78C64", "top": "tee", "top_color": "#F06292",
               "bottom": "skirt", "bottom_color": "#7E57C2", "shoes": "sneakers", "shoes_color": "#FFFFFF",
               "hat": "bow", "hat_color": "#7E57C2", "eyes": "sparkle", "neck": "", "extra": ""},
    "koko": {"fur": "#7A4E2D", "muzzle": "#694227", "top": "tee", "top_color": "#E8762B",
             "bottom": "shorts", "bottom_color": "#1E6FD9", "shoes": "sneakers", "shoes_color": "#222831",
             "hat": "cap", "hat_color": "#1E6FD9", "glasses": "", "neck": "", "extra": ""},
    "luna": {"fur": "#A39A93", "muzzle": "#8F857D", "top": "hoodie", "top_color": "#5C6BC0",
             "bottom": "pants", "bottom_color": "#3F3D56", "shoes": "boots", "shoes_color": "#5D4037",
             "hat": "flower", "hat_color": "#F48FB1", "eyes": "sleepy", "neck": "scarf", "neck_color": "#F48FB1",
             "extra": ""},
    "tito": {"fur": "#E0B060", "muzzle": "#C99A4E", "top": "vest", "top_color": "#2F9E44",
             "bottom": "pants", "bottom_color": "#2B2B33", "shoes": "boots", "shoes_color": "#3E2723",
             "hat": "crown", "hat_color": "#F2C230", "neck": "bowtie", "neck_color": "#B71C1C", "extra": "cape",
             "extra_color": "#B71C1C"},
}

# real capybaras (four legs, coarse reddish-brown fur), like the ones by the river
PRESETS.update({
    "wild": {"body": "real", "fur": "#9A5A2F", "muzzle": "#7E4826", "mood": "neutral", "hat": "", "glasses": "",
             "neck": "", "extra": "", "blush": False},
    "sir": {"body": "real", "fur": "#8C5530", "muzzle": "#704222", "mood": "happy", "hat": "tophat",
            "hat_color": "#222222", "neck": "bowtie", "neck_color": "#B71C1C", "glasses": "round",
            "glasses_color": "#C9A227", "extra": "", "blush": False},
    "onsen": {"body": "real", "fur": "#A8683A", "muzzle": "#8A532C", "mood": "sleepy", "hat": "flower",
              "hat_color": "#F48FB1", "neck": "", "glasses": "", "extra": "", "blush": True},
})
PRESETS.update({
    "lapulapu": {"body": "hero", "fur": "#9A6236", "muzzle": "#7E4E2A", "mood": "brave", "costume": "lapulapu",
                 "costume_color": "#8E1B1B", "weapon": "kampilan", "hat": "", "glasses": "", "neck": "", "extra": "",
                 "blush": False},
    "samurai": {"body": "hero", "fur": "#6B4A33", "muzzle": "#55392A", "mood": "angry", "costume": "samurai",
                "costume_color": "#2C3E66", "weapon": "katana", "hat": "", "glasses": "", "neck": "", "extra": "",
                "blush": False},
    "shogun": {"body": "hero", "fur": "#8A5A35", "muzzle": "#6E462A", "mood": "brave", "costume": "shogun",
               "costume_color": "#A3342B", "weapon": "katana", "hat": "", "glasses": "", "neck": "", "extra": "",
               "blush": False},
})
PRESET_INFO = {"lapulapu": ("Lapu-Lapu", "The hero of Mactan, kampilan raised"),
               "samurai": ("Samurai", "Dark lacquered armour and a katana"),
               "shogun": ("Shogun", "Red armour and the horned kabuto helmet"),
               "wild": ("Wild", "A real capybara, calm as anything"),
               "sir": ("Sir Capy", "A real capybara in his Sunday best"),
               "onsen": ("Onsen", "A real capybara, sleepy after a warm bath")}

# the old 2D headwear names, so a 2D avatar becomes the same avatar in 3D
_HAT_FROM_2D = {"bandana": "bandana", "bow": "bow", "flower": "flower", "cap": "cap", "crown": "crown"}


def look_from_2d(av: dict, preset: str = "") -> dict:
    """A 3D look for a 2D avatar (avatars.get): the preset's clothes in the avatar's own colours."""
    out = dict(DEFAULT_LOOK)
    out.update({k: v for k, v in PRESETS.get(preset or av.get("preset", ""), {}).items() if k != "body"})
    out["fur"] = av.get("fur", out["fur"])
    out["muzzle"] = QColor(out["fur"]).darker(112).name()
    out["top_color"] = av.get("hoodie", out["top_color"])
    acc = av.get("acc", "")
    if acc in _HAT_FROM_2D or acc == "":
        out["hat"] = _HAT_FROM_2D.get(acc, "")
        if acc:
            out["hat_color"] = av.get("acc_color", out["hat_color"])
    return out


def current_look(settings: dict, who: str) -> dict:
    """The 3D look of the avatar on screen (main) or the friend: as saved, or made from the 2D avatar."""
    from . import avatars
    saved = settings.get(f"look3d_{who}")
    if saved:
        return complete(saved)
    return look_from_2d(avatars.get(settings, who))


def complete(look: dict | None) -> dict:
    out = dict(DEFAULT_LOOK)
    out.update({k: v for k, v in (look or {}).items() if k in DEFAULT_LOOK and v is not None})
    return out


INK_DEFAULT = "#2A1A10"
_NOISE = [__import__("random").Random(7).random() ** 1.5 for _ in range(211)]   # fixed, so frames don't flicker


# --------------------------------------------------------------------------- #
# tiny vector maths
# --------------------------------------------------------------------------- #
def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return ((1, 0, 0), (0, c, -s), (0, s, c))


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, 0, s), (0, 1, 0), (-s, 0, c))


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))


def _mm(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def _mv(m, v):
    return (m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
            m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
            m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2])


_I = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def _norm(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _align_y(d):
    """A rotation that turns the +y axis into direction d."""
    d = _norm(d)
    y = (0.0, 1.0, 0.0)
    c = d[1]
    if c > 0.99999:
        return _I
    if c < -0.99999:
        return ((1, 0, 0), (0, -1, 0), (0, 0, -1))
    ax = _norm((y[1] * d[2] - y[2] * d[1], y[2] * d[0] - y[0] * d[2], y[0] * d[1] - y[1] * d[0]))
    s = math.sqrt(1 - c * c)
    x, yy, z = ax
    t = 1 - c
    return ((t * x * x + c, t * x * yy - s * z, t * x * z + s * yy),
            (t * x * yy + s * z, t * yy * yy + c, t * yy * z - s * x),
            (t * x * z - s * yy, t * yy * z + s * x, t * z * z + c))


# --------------------------------------------------------------------------- #
# shapes: each is a list of faces (points, normal); normals point outwards
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=16)
def _unit_sphere(lon: int, lat: int):
    """Faces of a unit sphere: (points, centroid) with the centroid pointing outwards."""
    pts = [[(math.sin(math.pi * j / lat) * math.cos(2 * math.pi * i / lon),
             math.cos(math.pi * j / lat),
             math.sin(math.pi * j / lat) * math.sin(2 * math.pi * i / lon)) for i in range(lon)] for j in range(lat + 1)]
    faces = []
    for j in range(lat):
        for i in range(lon):
            i2 = (i + 1) % lon
            if j == 0:
                quad = (pts[0][0], pts[1][i2], pts[1][i])
            elif j == lat - 1:
                quad = (pts[j][i], pts[j][i2], pts[lat][0])
            else:
                quad = (pts[j][i], pts[j][i2], pts[j + 1][i2], pts[j + 1][i])
            n = len(quad)
            faces.append((quad, (sum(q[0] for q in quad) / n, sum(q[1] for q in quad) / n,
                                 sum(q[2] for q in quad) / n)))
    return faces


def _seg_for(r) -> tuple[int, int]:
    """Fewer faces for small parts, more for big ones (smooth where it shows, fast where it doesn't)."""
    big = max(r)
    if big < 2.5:
        return (8, 5)
    if big < 6:
        return (12, 7)
    if big < 12:
        return (18, 11)
    return (26, 15)


class Mesh:
    """A bag of coloured faces in model space."""

    def __init__(self):
        self.faces: list = []          # (points, normal, QColor, shine, visible-side direction or None)
        self.anchor = (0.0, 90.0, 0.0)  # just above the head: where mood effects (hearts, "!") are drawn
        self.fx = ""
        self.outline = INK_DEFAULT

    def ellipsoid(self, c, r, color, rot=_I, shine=0.0, seg=None, cut=None, vis=None, rough=0.0):
        """cut: (axis 0-2, min, max) keeps only the part of the unit sphere with that coordinate in range.
        vis: for small details on a surface (eyes, cheeks, nostrils): the surface's outward direction there.
        The whole detail is skipped when that side of the head is turned away from the camera."""
        rx, ry, rz = r
        col = QColor(color)
        (a, b, cc), (d, e, f), (g, h, i) = rot
        cx, cy, cz = c
        ix, iy, iz = 1.0 / (rx or 1e-6), 1.0 / (ry or 1e-6), 1.0 / (rz or 1e-6)
        add = self.faces.append
        cols = None
        if rough:                      # coarse fur: every little face a slightly different shade
            cols = [_shade(col, 1.0 + rough * (v - 0.5)) for v in _NOISE]
        for fi, (quad, m) in enumerate(_unit_sphere(*(seg or _seg_for(r)))):
            if cut is not None and not (cut[1] <= m[cut[0]] <= cut[2]):
                continue
            pts = []
            for p in quad:
                x, y, z = p[0] * rx, p[1] * ry, p[2] * rz
                pts.append((a * x + b * y + cc * z + cx, d * x + e * y + f * z + cy, g * x + h * y + i * z + cz))
            x, y, z = m[0] * ix, m[1] * iy, m[2] * iz
            n = _norm((a * x + b * y + cc * z, d * x + e * y + f * z, g * x + h * y + i * z))
            add((pts, n, cols[(fi * 7 + int(cx * 13)) % len(_NOISE)] if cols else col, shine, vis))

    def limb(self, a, b, r, color, r2=None, shine=0.0, seg=None):
        """A rounded tube from a to b (an ellipsoid stretched along the line)."""
        d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        ln = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) or 1.0
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
        self.ellipsoid(mid, (r, ln / 2 + r * 0.55, r2 if r2 else r), color, _align_y(d), shine, seg)

    def torus(self, c, R, r, color, rot=_I, shine=0.0, seg=(20, 8), arc=2 * math.pi, vis=None):
        col = QColor(color)
        nu, nv = seg
        full = arc >= 2 * math.pi - 1e-6

        def at(i, j):
            u = arc * i / nu
            v = 2 * math.pi * j / nv
            cx, cz = math.cos(u) * R, math.sin(u) * R
            p = (cx + math.cos(u) * r * math.cos(v), r * math.sin(v), cz + math.sin(u) * r * math.cos(v))
            return p, (cx, 0.0, cz)
        for i in range(nu if full else nu - 1 + 1):
            if not full and i == nu:
                break
            for j in range(nv):
                ps = [at(i, j), at(i + 1, j), at(i + 1, j + 1), at(i, j + 1)]
                quad = [p for p, _ in ps]
                mid = [sum(q[k] for q in quad) / 4 for k in range(3)]
                ctr = [sum(q[1][k] for q in ps) / 4 for k in range(3)]
                n = _norm(_mv(rot, (mid[0] - ctr[0], mid[1] - ctr[1], mid[2] - ctr[2])))
                pts = [_mv(rot, q) for q in quad]
                self.faces.append(([(p[0] + c[0], p[1] + c[1], p[2] + c[2]) for p in pts], n, col, shine, vis))

    def cone(self, base, tip, r, color, seg=12, shine=0.0):
        col = QColor(color)
        d = (tip[0] - base[0], tip[1] - base[1], tip[2] - base[2])
        rot = _align_y(d)
        ring = [_mv(rot, (math.cos(2 * math.pi * i / seg) * r, 0, math.sin(2 * math.pi * i / seg) * r))
                for i in range(seg)]
        ring = [(p[0] + base[0], p[1] + base[1], p[2] + base[2]) for p in ring]
        ctr = ((base[0] * 2 + tip[0]) / 3, (base[1] * 2 + tip[1]) / 3, (base[2] * 2 + tip[2]) / 3)
        for i in range(seg):
            tri = [ring[i], ring[(i + 1) % seg], tip]
            m = [sum(p[k] for p in tri) / 3 for k in range(3)]
            self.faces.append((tri, _norm((m[0] - ctr[0], m[1] - ctr[1], m[2] - ctr[2])), col, shine, None))
        self.faces.append((list(reversed(ring)), _norm((-d[0], -d[1], -d[2])), col, shine, None))

    def disc(self, c, r, thick, color, rot=_I, seg=18, shine=0.0):
        """A short cylinder (brim, coin, eye shine…)."""
        self.ellipsoid(c, (r, thick, r), color, rot, shine, (seg, 6))


# --------------------------------------------------------------------------- #
# poses
# --------------------------------------------------------------------------- #
def _pose(mode: str, t: float, k: float):
    """Joint angles for a pose. Angles in radians; 0 = hanging straight down, + = forwards."""
    p = {"bob": 0.0, "lean": 0.0, "legL": 0.0, "legR": 0.0, "kneeL": 0.0, "kneeR": 0.0,
         "armL": 0.15, "armR": 0.15, "armL_out": 0.25, "armR_out": 0.25, "head_tilt": 0.0, "head_turn": 0.0,
         "mouth": 0.0, "blink": False, "sit": 0.0, "crouch": 0.0, "lie": 0.0}
    if mode == "run":
        s = math.sin(t)
        p.update(bob=abs(math.cos(t)) * 3.0, lean=0.12, legL=0.75 * s, legR=-0.75 * s,
                 kneeL=max(0.0, -s) * 0.9, kneeR=max(0.0, s) * 0.9,
                 armL=-0.85 * s, armR=0.85 * s, armL_out=0.2, armR_out=0.2, head_tilt=0.04 * math.sin(2 * t))
    elif mode == "idle":
        p.update(bob=math.sin(t) * 0.8, head_tilt=0.05 * math.sin(t * 0.5), armL=0.1, armR=0.1,
                 blink=(t % (2 * math.pi)) > 6.0)
    elif mode == "wave":
        p.update(bob=math.sin(t) * 0.8, armR=2.6, armR_out=0.55 + 0.35 * math.sin(t * 2), head_tilt=0.12)
    elif mode == "talk":
        p.update(bob=math.sin(t * 2) * 0.6, mouth=k, head_tilt=0.06 * math.sin(t),
                 armR=0.9 + 0.35 * math.sin(t * 1.5), armR_out=0.45, armL=0.1)
    elif mode == "jump":
        if k < 0.25:                      # crouch
            c = k / 0.25
            p.update(crouch=c, armL=-0.4 * c, armR=-0.4 * c, kneeL=0.9 * c, kneeR=0.9 * c, legL=0.45 * c,
                     legR=0.45 * c)
        else:                             # up with arms in the air, then down
            u = min(1.0, (k - 0.25) / 0.5)
            p.update(armL=2.7 * (1 - abs(1 - 2 * u)) + 0.4, armR=2.7 * (1 - abs(1 - 2 * u)) + 0.4,
                     armL_out=0.6, armR_out=0.6, legL=-0.2, legR=0.25, kneeL=0.5, kneeR=0.3, mouth=0.7,
                     head_tilt=-0.15)
    elif mode == "sleep":
        p.update(sit=1.0, blink=True, head_tilt=0.35 + 0.03 * math.sin(t), head_turn=0.0, armL=0.5, armR=0.5,
                 legL=1.45, legR=1.45, kneeL=0.0, kneeR=0.0, bob=math.sin(t) * 0.6)
    return p


# --------------------------------------------------------------------------- #
# the character
# --------------------------------------------------------------------------- #
def _shade(c: QColor, f: float) -> QColor:
    return QColor(max(0, min(255, int(c.red() * f))), max(0, min(255, int(c.green() * f))),
                  max(0, min(255, int(c.blue() * f))))


def build(look: dict, mode: str = "idle", t: float = 0.0, k: float = 0.0, mouth: float | None = None,
          mood: str | None = None) -> Mesh:
    """The avatar as a mesh, standing on y=0, facing +x (to the right), +z towards the viewer.
    mouth: open the mouth this much (0-1) whatever the pose (talking while running).
    mood: a key of MOODS (default: the look's own mood)."""
    L = complete(look)
    mood = mood or L["mood"]
    F = FACE.get(mood, FACE["neutral"])
    if mode == "jump" and mood in ("neutral", "sleepy", "sad"):
        F = FACE["excited"]
    if L["body"] in ("real", "hero"):
        return _build_real(L, F, mode, t, k, mouth, upright=L["body"] == "hero")
    P = _pose(mode, t, k)
    if mouth is not None:
        P["mouth"] = mouth
    m = Mesh()
    fur = QColor(L["fur"])
    fur_dark = fur.darker(135)
    muzzle = QColor(L["muzzle"])
    ink = QColor("#2A1A10")
    hs, ch, es, hgt = float(L["head"]), float(L["chubby"]), float(L["ears"]), float(L["height"])
    top, top_c = L["top"], QColor(L["top_color"])
    leg_len = 15 * hgt
    hip_y = 4 + leg_len - P["crouch"] * 5 + P["bob"]
    if P["sit"]:
        hip_y = 9 + P["bob"]

    # ---- legs and shoes ---------------------------------------------------- #
    bottom, bot_c = L["bottom"], QColor(L["bottom_color"])
    for side, z in (("L", -7.5 * ch), ("R", 7.5 * ch)):
        a, kn = P["leg" + side], P["knee" + side]
        hip = (0.0, hip_y, z)
        knee = (hip[0] + math.sin(a) * leg_len * 0.5, hip[1] - math.cos(a) * leg_len * 0.5, z)
        a2 = a - kn
        foot = (knee[0] + math.sin(a2) * leg_len * 0.5, knee[1] - math.cos(a2) * leg_len * 0.5, z)
        leg_col = bot_c if bottom == "pants" else fur
        m.limb(hip, knee, 6.2 * ch, bot_c if bottom in ("pants", "shorts") else fur)
        m.limb(knee, foot, 5.6, leg_col)
        shoes = L["shoes"]
        fwd = (math.cos(a2), math.sin(a2))
        foot_c = (foot[0] + fwd[0] * 4, foot[1] + fwd[1] * 4 - 1, z)
        frot = _rz(a2)
        if shoes == "none":
            m.ellipsoid(foot_c, (7.5, 3.6, 5.2), fur_dark, frot)
        else:
            sc = QColor(L["shoes_color"])
            if shoes == "boots":
                m.limb((foot[0], foot[1] + 6, z), foot, 6.2, sc, shine=0.2)
            m.ellipsoid(foot_c, (8.6, 4.2, 6.0), sc, frot, shine=0.25)
            if shoes == "sneakers":     # a white sole and a stripe
                m.ellipsoid((foot_c[0], foot_c[1] - 2.6, z), (8.9, 1.6, 6.2), QColor("#FAFAFA"), frot)
                m.ellipsoid((foot_c[0] - 1, foot_c[1] + 1.2, z + (5.2 if z > 0 else -5.2)), (4.5, 1.2, 0.9),
                            sc.darker(150), frot)
            elif shoes == "sandals":
                m.ellipsoid((foot_c[0], foot_c[1] - 2.4, z), (8.9, 1.5, 6.2), QColor("#6D4C41"), frot)

    # ---- body -------------------------------------------------------------- #
    body_c = (0.0, hip_y + 13 * hgt, 0.0)
    lean = P["lean"]
    brot = _rz(-lean)
    bw = 15.5 * ch
    body_col = top_c if top in ("hoodie", "tee") else fur
    m.ellipsoid(body_c, (bw, 17 * hgt, bw * 0.95), body_col, brot)
    m.ellipsoid((body_c[0] + 7 * ch, body_c[1] - 2, 0), (8.5 * ch, 11 * hgt, 10 * ch),
                muzzle.lighter(112) if top not in ("hoodie", "tee") else top_c, brot)   # belly
    if bottom in ("shorts", "pants"):
        m.ellipsoid((0, hip_y + 3, 0), (bw * 1.02, 7.5, bw * 0.97), bot_c, brot)
    elif bottom == "skirt":
        m.cone((0, hip_y + 9, 0), (0, hip_y - 6, 0), 0.1, bot_c)
        m.ellipsoid((0, hip_y + 1.5, 0), (bw * 1.25, 6.5, bw * 1.2), bot_c, brot, cut=(1, -1.0, 0.6))
    if top == "hoodie":
        m.ellipsoid((body_c[0] + 9 * ch, body_c[1] - 6, 0), (6 * ch, 5, 9), top_c.darker(115), brot)   # pocket
        m.ellipsoid((body_c[0] - 4, body_c[1] + 13, 0), (11, 7.5, 13 * ch), top_c.darker(108), brot)   # hood
        trim = QColor(L["top_trim"])
        for z in (-3.5, 3.5):            # drawstrings
            m.limb((body_c[0] + 11 * ch, body_c[1] + 10, z), (body_c[0] + 14 * ch, body_c[1] + 2, z), 0.9, trim)
    elif top == "vest" or top == "jacket":
        for z in (-1, 1):                # two front panels over the fur
            m.ellipsoid((body_c[0] - 1, body_c[1] + 1, z * 7.5 * ch), (bw * 0.98, 16 * hgt, 8.5 * ch), top_c,
                        brot)
        m.ellipsoid((body_c[0] - 6, body_c[1], 0), (10 * ch, 16 * hgt, 13 * ch), top_c, brot)
        if top == "jacket":
            m.ellipsoid((body_c[0] - 2, body_c[1] + 14, 0), (10, 4, 14 * ch), top_c.darker(115), brot)  # collar
    elif top == "tee":
        m.torus((body_c[0] + 2, body_c[1] + 14, 0), 8.5, 1.4, top_c.darker(118), _rz(-0.25 - lean))

    # ---- extras on the back -------------------------------------------------- #
    extra, ex_c = L["extra"], QColor(L["extra_color"])
    if extra == "backpack":
        m.ellipsoid((body_c[0] - 15 * ch, body_c[1] + 1, 0), (6.5, 13, 11 * ch), ex_c, brot, 0.1)
        m.ellipsoid((body_c[0] - 20 * ch, body_c[1] - 3, 0), (3.5, 6, 8), ex_c.darker(118), brot)
        for z in (-7, 7):
            m.limb((body_c[0] - 9, body_c[1] + 12, z * ch), (body_c[0] + 4, body_c[1] - 6, z * ch * 1.25), 1.3,
                   ex_c.darker(130))
    elif extra == "cape":
        sw = math.sin(t) * 0.12 if mode == "run" else 0.0
        m.ellipsoid((body_c[0] - 15 * ch, body_c[1] - 1, 0), (3, 18 * hgt, 17 * ch), ex_c, _rz(0.25 + lean + sw))
    elif extra == "wings":
        flap = math.sin(t * 2) * 0.35
        for z in (-1, 1):
            m.ellipsoid((body_c[0] - 15, body_c[1] + 6, z * 10), (4, 12, 2.5), QColor("#FFFFFF"),
                        _mm(_rx(z * (0.7 + flap)), _rz(0.5)), 0.2)

    # ---- arms ---------------------------------------------------------------- #
    sleeve = top in ("hoodie", "jacket")
    short_sleeve = top == "tee"
    for side, zs in (("L", -1), ("R", 1)):
        a, out = P["arm" + side], P["arm" + side + "_out"]
        sh = (body_c[0] + 1, body_c[1] + 8 * hgt, zs * (bw - 1.5))
        ln = 15.0
        d = (math.sin(a) * math.cos(out), -math.cos(a) * math.cos(out), zs * math.sin(out))
        if a > 1.6:                        # arm up in the air
            d = (math.sin(a) * 0.6, -math.cos(a), zs * math.sin(out))
        d = _norm(d)
        elbow = (sh[0] + d[0] * ln * 0.55, sh[1] + d[1] * ln * 0.55, sh[2] + d[2] * ln * 0.55)
        hand = (sh[0] + d[0] * ln, sh[1] + d[1] * ln, sh[2] + d[2] * ln)
        if sleeve:
            m.limb(sh, hand, 4.9, top_c)
            m.ellipsoid(hand, (3.0, 3.0, 4.6), top_c.darker(112), _align_y(d))      # cuff
        elif short_sleeve:
            m.limb(sh, elbow, 5.2, top_c)
            m.limb(elbow, hand, 4.0, fur)
        else:
            m.limb(sh, hand, 4.2, fur)
        m.ellipsoid((hand[0] + d[0] * 2.5, hand[1] + d[1] * 2.5, hand[2] + d[2] * 2.5), (4.0, 4.0, 4.0), fur.darker(108))

    # ---- head ---------------------------------------------------------------- #
    neck_y = body_c[1] + 15 * hgt
    hc = (body_c[0] + 3 + lean * 18, neck_y + 13 * hs, 0.0)
    hrot = _mm(_ry(P["head_turn"]), _rz(-P["head_tilt"] - F["tilt"]))
    m.fx = F["fx"]
    m.anchor = (hc[0] + 6 * hs, hc[1] + 20 * hs, 6.0)

    def H(x, y, z):                       # a point on the head (head space -> model space)
        q = _mv(hrot, (x * hs, y * hs, z * hs))
        return (hc[0] + q[0], hc[1] + q[1], hc[2] + q[2])

    def HV(x, y, z):                      # outward direction of the head surface at a point (for details)
        return _norm(_mv(hrot, (x - 4, y * 0.6, z)))

    def HE(x, y, z, r, col, rot=_I, shine=0.0, seg=None, cut=None, detail=False):
        m.ellipsoid(H(x, y, z), (r[0] * hs, r[1] * hs, r[2] * hs), col, _mm(hrot, rot), shine, seg, cut,
                    HV(x, y, z) if detail else None)

    HE(-1, 0, 0, (20, 15.5, 16.5), fur, seg=(32, 18))                 # skull: long and boxy, like a capybara
    HE(11, -4, 0, (13, 11.5, 13.5), muzzle, seg=(28, 16))              # the big blunt snout
    HE(23.0, -1.5, 0, (2.2, 2.9, 6.6), QColor("#5E3A26"), shine=0.4, detail=True)   # nose pad
    for z in (-3.0, 3.0):
        HE(24.9, -1.1, z, (0.8, 1.4, 1.4), QColor("#140C08"), detail=True)              # nostrils
    # ears
    ear_tip = _rz(-F["ears"])              # back and down when sad or angry, up when surprised
    for z in (-1, 1):
        HE(-7, 15 + F["ears"] * 2, z * 11, (4.2 * es, 5.2 * es, 3.0 * es), fur_dark, _mm(ear_tip, _rx(z * 0.4)))
        HE(-6, 15 + F["ears"] * 2, z * 12.3, (2.4 * es, 3.2 * es, 1.2), QColor("#E59A8A"),
           _mm(ear_tip, _rx(z * 0.4)), detail=True)
    # eyes
    eyes = L["eyes"]
    eye_c = QColor(L["eye_color"])
    for z in (-1, 1):
        ex, ey, ez = 9.5, 5.0, z * 10.8
        fe = F["eye"]
        if fe == "half" and not P["blink"]:
            eyes = "sleepy"
        elif fe == "wide":
            eyes = "wide"
        elif fe == "sparkle" and eyes == "round":
            eyes = "sparkle"
        if P["blink"] or eyes == "happy" or fe == "arc":
            m.torus(H(ex, ey - 1.0, ez), 3.2 * hs, 0.9 * hs, ink, _mm(hrot, _mm(_ry(-z * 0.9), _rx(math.pi / 2))),
                    seg=(10, 5), arc=math.pi, vis=HV(ex, ey, ez))
        elif eyes == "sleepy":
            HE(ex, ey, ez, (3.4, 2.4, 3.0), eye_c, shine=0.6, detail=True)
            HE(ex - 0.2, ey + 1.6, ez * 1.03, (3.8, 1.6, 3.2), fur.darker(110), detail=True)
        elif eyes == "wide":
            HE(ex, ey + 0.5, ez, (3.8, 4.6, 3.4), QColor("#FFFFFF"), detail=True)
            HE(ex + 1.6, ey + 0.5, ez * 1.08, (1.8, 2.2, 1.6), eye_c, shine=0.7, detail=True)
        else:
            big = 1.15 if eyes == "sparkle" else 1.0
            HE(ex, ey, ez, (3.2 * big, 3.8 * big, 3.0 * big), eye_c, shine=0.7, detail=True)
            HE(ex + 1.8, ey + 1.6, ez * 1.18, (1.1 * big, 1.1 * big, 1.0), QColor("#FFFFFF"), detail=True)
            if eyes == "sparkle":
                HE(ex + 2.2, ey - 1.4, ez * 1.2, (0.6, 0.6, 0.6), QColor("#FFFFFF"), detail=True)
        # eyebrows tell the mood: angry (down at the front), sad (up at the front), surprised (high)
        br = F["brow"]
        if br:
            lift = {"angry": (-2.6, 0.0), "brave": (-1.6, 0.0), "sad": (2.4, -0.6), "up": (0.8, 2.4)}[br]
            m.limb(H(ex - 3.5, ey + 6.5 + lift[1], ez * 1.02), H(ex + 3.0, ey + 6.5 + lift[0] + lift[1], ez * 0.98),
                   0.9 * hs, ink)
        if F["fx"] == "tear":               # a tear rolling down the cheek
            HE(ex + 1.0, ey - 5.5, ez * 1.12, (1.2, 2.2, 1.1), QColor("#7FC8F8"), shine=0.9, detail=True)
    if L["blush"] and F["blush"] > 0:
        b = F["blush"]
        for z in (-1, 1):
            HE(9, -4.5, z * 13.8, (3.6 * min(b, 1.4), 2.2 * min(b, 1.4), 1.4), QColor(240, 128, 140, 255), detail=True)
    elif F["fx"] == "anger":
        for z in (-1, 1):
            HE(9, -4.5, z * 13.8, (3.6, 2.2, 1.4), QColor(225, 90, 80), detail=True)
    # mouth: the mood's mouth, opening when talking
    mo = P["mouth"]
    shape = F["mouth"]
    if mo <= 0.05 and shape in ("grin", "o"):
        mo = 0.45 if shape == "grin" else 0.6
    if mo > 0.05 and shape == "o" and P["mouth"] <= 0.05:
        HE(19.5, -10.5, 0, (2.6, 2.8, 2.8), QColor("#5A1F1F"), detail=True)
    elif mo > 0.05:
        HE(19.5, -10.5, 0, (3.4, 1.4 + 3.4 * mo, 5.0), QColor("#5A1F1F"), detail=True)
        HE(20.4, -11.5 - 1.5 * mo, 0, (2.0, 1.1 * mo + 0.3, 3.2), QColor("#E57373"), detail=True)
    elif shape == "frown":
        m.torus(H(19.6, -12.0, 0), 2.6 * hs, 0.6 * hs, ink, _mm(hrot, _mm(_rz(-0.4), _rx(-math.pi / 2))),
                seg=(8, 4), arc=math.pi, vis=HV(20.0, -9.8, 0))
    elif shape == "flat":
        m.limb(H(20.5, -10.4, -2.6), H(20.5, -10.4, 2.6), 0.6 * hs, ink)
    else:
        m.torus(H(20.0, -9.8, 0), 2.6 * hs, 0.6 * hs, ink, _mm(hrot, _mm(_rz(-0.4), _rx(math.pi / 2))),
                seg=(8, 4), arc=math.pi, vis=HV(20.0, -9.8, 0))

    _headwear(m, L, H, HE, hrot, hs)

    # ---- neck ---------------------------------------------------------------------- #
    nk, nk_c = L["neck"], QColor(L["neck_color"])
    ny = neck_y + 1
    if nk == "scarf":
        m.torus((body_c[0] + 2, ny, 0), 10.5 * ch, 3.4, nk_c, _rz(-0.2))
        m.limb((body_c[0] + 9, ny - 1, 6), (body_c[0] + 11, ny - 13, 8), 2.6, nk_c.darker(108))
    elif nk == "bowtie":
        for zz in (-1, 1):
            m.ellipsoid((body_c[0] + 13.5 * ch, ny - 1, zz * 3.6), (1.6, 2.8, 3.4), nk_c, _rx(zz * 0.4), 0.2)
        m.ellipsoid((body_c[0] + 14 * ch, ny - 1, 0), (1.8, 1.6, 1.6), nk_c.darker(120))
    elif nk == "tie":
        m.ellipsoid((body_c[0] + 14 * ch, ny - 1.5, 0), (1.6, 1.8, 2.0), nk_c.darker(115))
        m.ellipsoid((body_c[0] + 14.8 * ch, ny - 10, 0), (1.4, 7.5, 2.8), nk_c, _rz(-0.08), 0.2)
    elif nk == "chain":
        m.torus((body_c[0] + 3, ny - 2, 0), 11 * ch, 0.9, nk_c, _rz(-0.35), 0.9, seg=(22, 4))
        m.ellipsoid((body_c[0] + 14 * ch, ny - 9, 0), (1.2, 3.0, 3.0), nk_c, shine=0.9)
    return m


def _headwear(m: "Mesh", L: dict, H, HE, hrot, hs: float):
    """Hats and glasses, in the cartoon head's coordinates (other heads map their own space onto it)."""
    # ---- headwear --------------------------------------------------------------- #
    hat, hat_c = L["hat"], QColor(L["hat_color"])
    if hat == "cap":
        HE(0, 7, 0, (18.5, 13, 17.5), hat_c, cut=(1, -0.05, 1.01), shine=0.15)
        HE(14, 9, 0, (14, 1.6, 13), hat_c.darker(115), _rz(-0.12))
        HE(0, 19.5, 0, (2.2, 1.6, 2.2), hat_c.darker(125))
    elif hat == "beanie":
        HE(-1, 7, 0, (19.8, 14.5, 18.4), hat_c, cut=(1, -0.1, 1.01))
        m.torus(H(-1, 6, 0), 18.4 * hs, 2.4 * hs, hat_c.darker(115), _mm(hrot, _rz(0.05)))
        HE(-2, 23, 0, (4.6, 4.6, 4.6), QColor("#FAFAFA"))
    elif hat == "crown":
        m.torus(H(-1, 13, 0), 10.5 * hs, 1.6 * hs, hat_c, hrot, 0.7)
        for i in range(5):
            a = 2 * math.pi * i / 5
            base = H(-1 + math.cos(a) * 10.5, 13.5, math.sin(a) * 10.5)
            tip = H(-1 + math.cos(a) * 11.5, 21, math.sin(a) * 11.5)
            m.cone(base, tip, 2.8 * hs, hat_c, 8, 0.7)
            m.ellipsoid(tip, (1.3, 1.3, 1.3), QColor("#E53935"), shine=0.8)
    elif hat == "bandana":
        HE(-1, 5.5, 0, (19.6, 12.5, 17.9), hat_c, cut=(1, 0.05, 1.01))
        for zz in (-1, 1):
            HE(-21, 3 - zz, zz * 3, (2.2, 5.5, 2.4), hat_c.darker(110), _rz(0.6 + zz * 0.3))
        for i in range(6):               # white dots
            a = 0.4 + i * 0.45
            HE(math.cos(a) * 12, 13, math.sin(a) * 12 - 3, (1.4, 0.6, 1.4), QColor("#FFFFFF"))
    elif hat == "bow":
        for zz in (-1, 1):
            HE(-2, 16.5, 8 + zz * 4.5, (2.4, 4.0, 5.0), hat_c, _rx(zz * 0.5), 0.2)
        HE(-2, 16.5, 8, (2.6, 2.2, 2.2), hat_c.darker(118))
    elif hat == "flower":
        for i in range(5):
            a = 2 * math.pi * i / 5
            HE(-3 + math.cos(a) * 3.8, 13.5 + math.sin(a) * 3.8, 12, (2.6, 2.6, 1.2), hat_c)
        HE(-3, 13.5, 13, (1.8, 1.8, 1.0), QColor("#FFD54A"))
    elif hat == "tophat":
        HE(-1, 13.5, 0, (17, 1.4, 17), hat_c.darker(105), shine=0.2)
        HE(-1, 22, 0, (10.5, 9, 10.5), hat_c, shine=0.3, seg=(16, 8))
        m.torus(H(-1, 16, 0), 10.6 * hs, 1.3 * hs, QColor("#B71C1C"), hrot)
    elif hat == "headphones":
        m.torus(H(-2, 3, 0), 17.5 * hs, 1.6 * hs, hat_c.darker(110), _mm(hrot, _rx(math.pi / 2)), 0.4,
                arc=math.pi)
        for zz in (-1, 1):
            HE(-2, 1, zz * 17, (5.5, 6.5, 3.2), hat_c, shine=0.4)
    elif hat == "party":
        m.cone(H(-2, 13, 2), H(-4, 31, 2), 7 * hs, hat_c, 14, 0.2)
        HE(-4, 31.5, 2, (2.4, 2.4, 2.4), QColor("#FFD54A"))

    # ---- glasses ------------------------------------------------------------------ #
    gl, gl_c = L["glasses"], QColor(L["glasses_color"])
    if gl:
        for z in (-1, 1):
            if gl == "shades" or gl == "star":
                lens = QColor("#151515") if gl == "shades" else QColor("#E91E63")
                HE(11.5, 5, z * 11.5, (2.0, 4.6, 5.2), lens, _ry(-z * 0.55), 0.9)
            m.torus(H(11.5, 5, z * 11.5), 4.6 * hs, 0.7 * hs, gl_c, _mm(hrot, _mm(_ry(-z * 0.55), _rz(math.pi / 2))),
                    0.6, seg=(14, 5))
        m.limb(H(13.5, 5.5, -6), H(13.5, 5.5, 6), 0.6 * hs, gl_c)



# --------------------------------------------------------------------------- #
# real capybaras: on four legs, or standing up like a warrior
# --------------------------------------------------------------------------- #
def _real_pose(mode: str, t: float, k: float, upright: bool) -> dict:
    p = {"bob": 0.0, "FL": 0.0, "FR": 0.0, "RL": 0.0, "RR": 0.0, "kneeF": 0.0, "head_tilt": 0.0, "head_turn": 0.0,
         "mouth": 0.0, "blink": False, "lie": 0.0, "lift": 0.0, "armL": 0.15, "armR": 0.15, "armL_out": 0.2,
         "armR_out": 0.2, "lifted": False, "ear": 0.0}
    s = math.sin(t)
    if mode == "run":
        if upright:
            p.update(bob=abs(math.cos(t)) * 2.5, RL=0.7 * s, RR=-0.7 * s, armL=-0.7 * s, armR=0.7 * s)
        else:                              # a trot: diagonal legs together
            p.update(bob=abs(math.cos(t)) * 2.2, FL=0.55 * s, RR=0.55 * s, FR=-0.55 * s, RL=-0.55 * s,
                     head_tilt=0.05 * math.sin(2 * t))
    elif mode == "idle":
        p.update(bob=math.sin(t) * 0.6, ear=0.15 * max(0.0, math.sin(t * 3)), blink=(t % (2 * math.pi)) > 6.0)
    elif mode == "talk":
        p.update(bob=math.sin(2 * t) * 0.5, mouth=k, head_tilt=-0.08 + 0.05 * math.sin(t),
                 armR=0.8 + 0.3 * math.sin(1.5 * t), armR_out=0.35)
    elif mode == "wave":
        p.update(bob=math.sin(t) * 0.6, lifted=True, armR=2.7, armR_out=0.35 + 0.15 * math.sin(2 * t),
                 FR=-1.1 + 0.35 * math.sin(2 * t), kneeF=1.0, head_tilt=-0.1)
    elif mode == "jump":
        c = min(1.0, k / 0.25)
        up = k > 0.25
        p.update(lift=(0 if not up else 4.0), FL=-0.6 if up else 0.3 * c, FR=-0.6 if up else 0.3 * c,
                 RL=0.7 if up else -0.3 * c, RR=0.7 if up else -0.3 * c, mouth=0.5 if up else 0.0,
                 lifted=up, armL=2.6 if up else -0.3, armR=2.7 if up else -0.3, armL_out=0.5, armR_out=0.4)
    elif mode == "sleep":
        p.update(lie=1.0, blink=True, head_tilt=0.3 + 0.03 * s, bob=0.4 * s, armL=0.9, armR=0.9)
    return p


def _build_real(L: dict, F: dict, mode: str, t: float, k: float, mouth, upright: bool) -> Mesh:
    P = _real_pose(mode, t, k, upright)
    if mouth is not None:
        P["mouth"] = mouth
    m = Mesh()
    fur = QColor(L["fur"])
    face = QColor(L["muzzle"])
    leg = fur.darker(122)
    sole = QColor("#2E211B")
    m.outline = fur.darker(260).name()
    R = 0.38                                         # how coarse the fur looks
    bob, lift = P["bob"], P["lift"]
    cos_ = L["costume"]

    def E(c, r, col, rot=_I, shine=0.0, rough=R, seg=None):
        m.ellipsoid(c, r, col, rot, shine, seg, None, None, rough)

    def foot(c, a=0.0):                              # a webbed foot with three dark toes
        E((c[0] + 2, c[1], c[2]), (5.2, 2.2, 3.6), sole, _rz(a), 0.15, 0.1)
        for dz in (-1.8, 0.0, 1.8):
            E((c[0] + 6.2, c[1] - 0.4, c[2] + dz), (1.5, 1.1, 1.0), sole.darker(120), shine=0.3, rough=0.0)

    def leg_(hip, a, length, r1, r2, knee=0.0):
        kn = (hip[0] + math.sin(a) * length * 0.5, hip[1] - math.cos(a) * length * 0.5, hip[2])
        a2 = a - knee
        ft = (kn[0] + math.sin(a2) * length * 0.5, kn[1] - math.cos(a2) * length * 0.5, hip[2])
        m.limb(hip, kn, r1, leg)
        m.limb(kn, ft, r2, leg)
        foot((ft[0], ft[1] + 1.2, ft[2]), a2 * 0.3)
        return ft

    if upright:
        # ---- standing: short strong legs, a pear-shaped body, arms ------------------------- #
        y0 = lift + bob
        for side, z in (("L", -7.5), ("R", 7.5)):
            E((0, 17 + y0, z), (9.5, 10, 6.8), fur)                       # haunch
            leg_((1, 14 + y0, z), P["R" + side], 13, 4.6, 3.8)
        E((0, 31 + y0, 0), (15.5, 17, 14), fur)                            # belly
        E((2, 46 + y0, 0), (13, 13, 12), fur)                              # chest
        E((4, 57 + y0, 0), (9, 8.5, 9), fur)                               # neck
        hc = (8, 69 + y0, 0.0)
        hs = 0.95
        shoulders = []
        for side, zs in (("L", -1), ("R", 1)):
            a, out = P["arm" + side], P["arm" + side + "_out"]
            sh = (3, 51 + y0, zs * 11.5)
            d = (math.sin(a) * math.cos(out), -math.cos(a) * math.cos(out), zs * math.sin(out))
            if a > 1.6:
                d = (math.sin(a) * 0.5, -math.cos(a), zs * math.sin(out))
            d = _norm(d)
            hand = (sh[0] + d[0] * 17, sh[1] + d[1] * 17, sh[2] + d[2] * 17)
            m.limb(sh, hand, 4.2, fur)
            E((hand[0] + d[0] * 2, hand[1] + d[1] * 2, hand[2] + d[2] * 2), (3.4, 3.6, 3.2), leg.darker(110), shine=0.1)
            shoulders.append((sh, hand, d))
        body = {"waist": 25 + y0, "chest": 46 + y0, "shoulders": shoulders, "y0": y0}
        _costume(m, L, body, P, t, mode)
        _weapon(m, L, body, P, mode)
    else:
        # ---- on four legs: a big barrel body, short legs, the head held forward ------------- #
        lie = P["lie"]
        y0 = bob + lift - lie * 11
        E((-4, 30 + y0, 0), (29, 17.5, 16.5), fur, seg=(26, 15))           # barrel
        E((-23, 31 + y0, 0), (16, 18, 16), fur)                             # rump
        E((15, 29 + y0, 0), (14, 16, 13.5), fur)                            # chest
        E((24, 37 + y0, 0), (10.5, 12, 10), fur, _rz(-0.5))                # neck
        if lie < 0.5:
            for z in (-9, 9):
                side = "L" if z < 0 else "R"
                leg_((15, 20 + y0, z), P["F" + side], 17, 4.4, 3.4, P["kneeF"] if side == "R" else 0.0)
                E((-23, 25 + y0, z * 1.05), (11, 12, 6.5), fur)                # haunch
                leg_((-20, 18 + y0, z), P["R" + side], 15, 4.6, 3.6)
        else:                                                                  # lying down: paws tucked in front
            for z in (-6, 6):
                foot((22, 3, z))
        hc = (36, 45 + y0 - lie * 6, 0.0)
        hs = 1.0
        if cos_ == "wrap":
            body = {"waist": 25 + y0, "chest": 30 + y0, "shoulders": [], "y0": y0, "four": True}
            _costume(m, L, body, P, t, mode)

    # ---- the head: long and boxy, small ears and eyes high up, a big blunt nose ------------- #
    hrot = _mm(_ry(P["head_turn"]), _rz(-P["head_tilt"] - F["tilt"] - (0.35 if not upright else 0.02)))

    def H(x, y, z):
        q = _mv(hrot, (x * hs, y * hs, z * hs))
        return (hc[0] + q[0], hc[1] + q[1], hc[2] + q[2])

    def HV(x, y, z):
        return _norm(_mv(hrot, (x - 6, y * 0.8, z)))

    def HE(x, y, z, r, col, rot=_I, shine=0.0, detail=False, rough=0.0, seg=None, cut=None):
        m.ellipsoid(H(x, y, z), (r[0] * hs, r[1] * hs, r[2] * hs), col, _mm(hrot, rot), shine, seg, cut,
                    HV(x, y, z) if detail else None, rough)

    HE(0, 0, 0, (13.5, 10.5, 9.6), fur, rough=R, seg=(26, 15))               # skull
    HE(11, -2.5, 0, (11.5, 9.6, 8.8), face, rough=R * 0.8, seg=(24, 14))     # long face
    HE(19.5, -3.2, 0, (5.6, 8.8, 8.2), face, rough=R * 0.6)                  # the square front of the muzzle
    HE(24.2, -0.6, 0, (2.0, 5.0, 6.6), QColor("#3A2C27"), shine=0.35, detail=True)    # nose
    for z in (-2.9, 2.9):
        HE(25.4, 0.6, z, (0.7, 1.9, 1.3), QColor("#120C0A"), detail=True)              # nostrils
    mo = P["mouth"]
    shape = F["mouth"]
    if mo <= 0.05 and shape in ("grin", "o"):
        mo = 0.35
    if F["fx"] == "anger" and mo <= 0.05:
        mo = 0.55                                    # angry: mouth open, big front teeth showing
    jaw_y = -10.0 - 3.0 * mo
    HE(16, jaw_y, 0, (8.5, 3.0, 6.8), face.darker(108), rough=R * 0.5)       # lower jaw
    if mo > 0.05:
        HE(19.5, -9.0 - 1.4 * mo, 0, (4.2, 1.2 + 2.2 * mo, 5.2), QColor("#3C1414"), detail=True)
        for z in (-1.1, 1.1):
            HE(23.6, -8.0 - 0.8 * mo, z, (0.9, 2.2, 1.0), QColor("#F4EBD8"), shine=0.4, detail=True)  # incisors
    else:
        m.limb(H(23.5, -8.6, -4.5), H(23.8, -8.4, 4.5), 0.45 * hs, QColor("#24160F"))
    # ears: small, round, on top
    for z in (-1, 1):
        rot = _mm(_rz(-F["ears"] * 1.2 - P["ear"]), _rx(z * 0.25))
        HE(-7, 9.5 + F["ears"] * 1.5, z * 6.2, (2.6, 3.4, 2.0), fur.darker(150), rot, rough=0.2)
        HE(-6.4, 9.6 + F["ears"] * 1.5, z * 7.0, (1.5, 2.2, 0.8), QColor("#5A3A32"), rot, detail=True)
    # eyes: small and high, with heavy lids
    ink = QColor("#140C08")
    for z in (-1, 1):
        ex, ey, ez = 5.0, 4.6, z * 7.9
        fe = F["eye"]
        if P["blink"] or fe == "arc":
            m.torus(H(ex, ey - 0.6, ez), 2.0 * hs, 0.55 * hs, ink,
                    _mm(hrot, _mm(_ry(-z * 1.0), _rx(math.pi / 2))), seg=(8, 4), arc=math.pi, vis=HV(ex, ey, ez))
        else:
            big = 1.35 if fe == "wide" else 1.0
            HE(ex, ey, ez, (1.9 * big, 1.7 * big, 1.4), ink, shine=0.9, detail=True)
            HE(ex + 0.8, ey + 0.7, ez * 1.1, (0.5, 0.5, 0.4), QColor("#FFFFFF"), detail=True)
            if fe == "half":                                   # heavy, sad or sleepy lids
                HE(ex - 0.2, ey + 1.2, ez * 1.03, (2.4, 1.3, 1.6), fur.darker(115), detail=True)
            if fe == "sparkle":
                HE(ex + 1.2, ey - 0.6, ez * 1.12, (0.35, 0.35, 0.3), QColor("#FFFFFF"), detail=True)
        br = F["brow"]
        if br:                                                  # fur ridges over the eyes
            lift_ = {"angry": (-1.8, 0.0), "brave": (-1.2, 0.0), "sad": (1.8, -0.4), "up": (0.6, 1.6)}[br]
            m.limb(H(ex - 3.0, ey + 3.2 + lift_[1], ez * 1.04), H(ex + 2.6, ey + 3.2 + lift_[0] + lift_[1], ez * 0.98),
                   0.75 * hs, fur.darker(175))
        if F["fx"] == "tear":                                   # tears running down the cheek
            for i, dy in enumerate((2.2, 5.0, 7.8)):
                HE(ex + 0.6 + i * 0.3, ey - dy, ez * (1.12 + i * 0.03), (0.6, 1.3, 0.6), QColor("#BFE6FF"),
                   shine=1.0, detail=True)
    if L["blush"] and F["blush"] > 0:
        for z in (-1, 1):
            HE(10, -4, z * 9.0, (2.6, 1.6, 1.0), QColor(220, 120, 120), detail=True)
    # whiskers
    wc = QColor("#D9CBB8")
    for z in (-1, 1):
        for dy, dz in ((0.0, 2.0), (-2.0, 1.0), (1.8, 2.6)):
            a = H(20, -3 + dy, z * 7.2)
            b = H(27, -3.5 + dy * 1.8, z * (9 + dz))
            m.limb(a, b, 0.18 * hs, wc, seg=(4, 3))
    # hats and glasses: the cartoon head's coordinates, scaled onto this smaller head
    if cos_ != "shogun":
        sc = 0.6

        def H2(x, y, z):
            return H(x * sc + 1.0, y * sc + 0.5, z * sc)

        def HE2(x, y, z, r, col, rot=_I, shine=0.0, seg=None, cut=None, detail=False):
            m.ellipsoid(H2(x, y, z), (r[0] * sc * hs, r[1] * sc * hs, r[2] * sc * hs), col, _mm(hrot, rot), shine,
                        seg, cut)
        _headwear(m, L, H2, HE2, hrot, sc * hs)
    if cos_ == "shogun":
        _kabuto(m, L, H, HE, hrot, hs, crest=True)
    elif cos_ == "samurai":                          # a hachimaki headband, tails flying behind
        m.torus(H(0, 4.5, 0), 10.6 * hs, 1.3 * hs, QColor("#EDE6D6"), _mm(hrot, _rz(0.15)), 0.2, seg=(22, 4))
        HE(1, 5.2, 0, (11.2, 0.6, 9.9), QColor("#B23A2E"), _rz(0.15))
        for z in (-1, 1):
            m.limb(H(-11, 3, z * 1.5), H(-19, -2 + z * 2, z * 3), 1.0 * hs, QColor("#EDE6D6"))
    m.fx = F["fx"] if F["fx"] != "tear" else ""
    m.anchor = H(2, 16, 4)
    return m


def _bands(m, c, R, y, rot, cols, r=0.9):
    """Stacked rings: beads, woven stripes."""
    for i, col in enumerate(cols):
        m.torus((c[0], y + i * r * 2.0, c[2]), R, r, QColor(col), rot, 0.35, seg=(20, 4))


def _costume(m: Mesh, L: dict, body: dict, P: dict, t: float, mode: str):
    cos_ = L["costume"]
    main = QColor(L["costume_color"])
    w, ch = body["waist"], body["chest"]
    if body.get("four"):                                  # the woven wrap round a four-legged capybara
        for x in (-12, 0, 12):
            m.torus((x, ch + 1, 0), 15.5, 1.6, main if x != 0 else QColor("#C9A227"), _rx(math.pi / 2) and _rz(math.pi / 2),
                    0.2, seg=(22, 5))
        return
    if cos_ == "lapulapu" or cos_ == "wrap":
        # a woven skirt (bahag) with gold and black stripes, a sash, beaded chest armour
        m.ellipsoid((0.5, w - 5, 0), (17, 8.5, 15), main, _I, 0.1)
        m.ellipsoid((0.5, w - 11, 0), (17.5, 7.5, 15.5), main.darker(108), _I, 0.1, cut=(1, -1.0, 0.2))
        for i, col in enumerate(("#C9A227", "#1B1B1B", "#C9A227")):
            m.torus((0.5, w - 9.5 - i * 1.6, 0), 16.4, 0.55, QColor(col), _I, 0.3, seg=(24, 3))
        m.ellipsoid((13, w - 13, 0), (2.5, 9, 5), main.darker(125), _rz(-0.08), 0.1)        # front flap
        m.ellipsoid((13.5, w - 15, 0), (2.6, 1.0, 5.2), QColor("#C9A227"), _rz(-0.08), 0.4)
        m.torus((0.5, w + 1.5, 0), 15.8, 1.6, QColor("#5B1414"), _I, 0.2, seg=(24, 5))       # sash
        if cos_ == "lapulapu":
            m.ellipsoid((3, ch - 1, 0), (13.6, 11.5, 12.6), QColor("#6B4A26"), _I, 0.3)        # leather vest
            for i, col in enumerate(("#C9A227", "#7A1E1E", "#C9A227")):                     # bead rows
                m.torus((3.5, ch - 6 + i * 3.4, 0), 13.2 - i * 0.4, 0.6, QColor(col), _rz(-0.08), 0.5, seg=(22, 3))
            for i in range(2):                                                               # bead necklaces
                m.torus((5, ch + 7 - i * 2.0, 0), 8.6 + i * 1.6, 0.6, QColor(("#E8D9A8", "#C9A227")[i]),
                        _rz(-0.45), 0.6, seg=(20, 3))
            m.ellipsoid((14.5, ch - 1, 0), (1.4, 3.0, 3.0), QColor("#C9A227"), shine=0.8)     # gold plaque
        for sh, hand, d in body["shoulders"]:                                               # arm bands
            for f, col in ((0.55, "#C9A227"), (0.85, "#7A1E1E")):
                c = (sh[0] + (hand[0] - sh[0]) * f, sh[1] + (hand[1] - sh[1]) * f, sh[2] + (hand[2] - sh[2]) * f)
                m.torus(c, 4.6, 1.0, QColor(col), _align_y(d), 0.5, seg=(14, 4))
    elif cos_ in ("samurai", "shogun"):
        lace = QColor("#B23A2E") if cos_ == "samurai" else QColor("#24345E")
        dark = main.darker(150)
        m.ellipsoid((2, ch - 2, 0), (16.5, 14, 15.2), main, _I, 0.55)                         # do (chest plate)
        for i in range(4):                                                                   # lacing rows
            m.torus((2, ch - 10 + i * 4.0, 0), 15.6 - abs(i - 1.5) * 0.6, 0.6, lace, _I, 0.2, seg=(24, 4))
        m.torus((1, w + 1, 0), 17.8, 2.6, QColor("#1F2A44") if cos_ == "shogun" else QColor("#6B2A1E"), _I, 0.2,
                seg=(24, 6))                                                                 # obi
        for i in range(8):                                                                   # kusazuri plates
            a = 2 * math.pi * i / 8
            c = (1 + math.cos(a) * 15, w - 7, math.sin(a) * 14)
            rot = _mm(_ry(-a), _rz(0.0))
            m.ellipsoid(c, (1.1, 7.5, 5.6), main, _mm(rot, _rz(0.0)), 0.5)
            m.torus((c[0], w - 6, c[2]), 6.0, 0.5, lace, _mm(rot, _rz(math.pi / 2)), seg=(10, 3))
        for sh, hand, d in body["shoulders"]:                                               # sode + kote
            zs = 1 if sh[2] > 0 else -1
            m.ellipsoid((sh[0], sh[1] - 3, sh[2] + zs * 2.5), (8.5, 7.5, 2.4), main, _rx(zs * 0.35), 0.5)
            m.torus((sh[0], sh[1] - 4, sh[2] + zs * 3.2), 6.5, 0.5, lace, _mm(_rx(zs * 0.35), _rz(0)), seg=(12, 3))
            mid = ((sh[0] + hand[0]) / 2, (sh[1] + hand[1]) / 2, (sh[2] + hand[2]) / 2)
            m.limb(mid, hand, 4.6, dark, shine=0.4)
        for z in (-7.5, 7.5):                                                                # suneate (shin guards)
            m.ellipsoid((3.5, 7 + body["y0"], z), (2.6, 6, 4.2), dark, _I, 0.4)


def _kabuto(m: Mesh, L: dict, H, HE, hrot, hs: float, crest: bool):
    """A samurai helmet: dome, flared neck guard, and for the shogun the gold horns and the red-orange disc."""
    main = QColor(L["costume_color"])
    iron = QColor("#2B2B30") if not crest else QColor("#8A8F98")
    HE(-1, 6, 0, (13.8, 9.5, 10.8), iron, shine=0.7, seg=(22, 12), cut=(1, -0.15, 1.01))      # dome
    for i in range(3):                                                                    # shikoro: neck guard
        m.torus(H(-4, 4 - i * 2.4, 0), (11.6 + i * 1.6) * hs, 1.2 * hs, main if i % 2 == 0 else main.darker(130),
                _mm(hrot, _rz(0.3)), 0.4, seg=(22, 4), arc=math.pi * 1.2)
    HE(9.5, 6.5, 0, (3.0, 1.4, 10.5), iron.darker(115), _rz(-0.3), 0.6)                # visor
    if crest:
        gold = QColor("#D4AF37")
        for z in (-1, 1):                                                                 # kuwagata horns
            m.limb(H(10, 12, z * 2.5), H(11, 21, z * 8.5), 1.0 * hs, gold, shine=0.9)
            m.limb(H(11, 21, z * 8.5), H(8, 27, z * 10.5), 0.8 * hs, gold, shine=0.9)
        HE(13.5, 15, 0, (1.2, 4.6, 4.6), QColor("#E8762B"), shine=0.5)                     # maedate disc
        HE(12, 11.5, 0, (1.6, 2.2, 3.4), gold, shine=0.9)
    for z in (-1, 1):                                                                     # fukigaeshi wings
        HE(4, 3, z * 12.5, (5, 4.5, 1.2), main, _ry(z * 0.4), 0.5)
    m.limb(H(6, -9, -8), H(10, -14, 0), 0.6 * hs, QColor("#E6DCC8"))                     # chin cord
    m.limb(H(6, -9, 8), H(10, -14, 0), 0.6 * hs, QColor("#E6DCC8"))


def _weapon(m: Mesh, L: dict, body: dict, P: dict, mode: str):
    wp = L["weapon"]
    if not wp or not body["shoulders"]:
        return
    steel = QColor("#C9CED6")
    sh, hand, d = body["shoulders"][1]                       # the right hand (towards you)
    raised = P["lifted"]
    if wp == "katana" and not raised:                        # sheathed at the left hip
        y = body["waist"] + 1
        m.limb((-14, y - 8, -14), (16, y + 2, -15), 1.5, QColor("#5A1414"), shine=0.5)         # saya
        m.limb((16, y + 2, -15), (24, y + 5, -15.5), 1.4, QColor("#1B1B1B"))                    # tsuka
        m.ellipsoid((16, y + 2, -15), (0.6, 2.6, 2.6), QColor("#C9A227"), _rz(-0.32), 0.8)      # tsuba
        return
    # in the hand: up in the air when raised, otherwise held down by the side, point forward
    up = _norm((0.35, 1.0, 0.05)) if raised else _norm((0.85, -0.35, 0.1))
    g = (hand[0] + d[0] * 2, hand[1] + d[1] * 2, hand[2] + d[2] * 2)
    hilt_end = (g[0] - up[0] * 6, g[1] - up[1] * 6, g[2] - up[2] * 6)
    m.limb(hilt_end, g, 1.3, QColor("#2A1A12") if wp == "katana" else QColor("#6B3A1E"))
    if wp == "katana":
        m.ellipsoid(g, (2.8, 0.6, 2.8), QColor("#C9A227"), _align_y(up), 0.8)
        tip = (g[0] + up[0] * 40, g[1] + up[1] * 40, g[2] + up[2] * 40)
        m.limb(g, tip, 0.9, steel, r2=1.6, shine=1.0)
    else:                                                    # kampilan: a long blade, wider and forked at the tip
        m.ellipsoid(g, (3.2, 0.9, 2.4), QColor("#B08D3C"), _align_y(up), 0.7)
        tip = (g[0] + up[0] * 36, g[1] + up[1] * 36, g[2] + up[2] * 36)
        m.limb(g, tip, 1.0, steel, r2=2.6, shine=1.0)
        side = _norm((-up[1], up[0], 0.0))
        for f in (-1, 1):
            a = (tip[0] + side[0] * f * 1.6, tip[1] + side[1] * f * 1.6, tip[2])
            m.cone(a, (a[0] + up[0] * 5 + side[0] * f * 1.5, a[1] + up[1] * 5 + side[1] * f * 1.5, a[2]), 1.4, steel, 6,
                   1.0)


# --------------------------------------------------------------------------- #
# mood effects drawn over the picture (hearts, sparkles, anger mark, "!")
# --------------------------------------------------------------------------- #
def _draw_fx(p: QPainter, fx: str, x: float, y: float, u: float, t: float):
    from PySide6.QtGui import QFont, QPainterPath
    p.setRenderHint(QPainter.Antialiasing)
    if fx == "hearts":
        for i, (dx, dy, s) in enumerate(((6, -2, 5.5), (15, -11, 4.0))):
            bob = math.sin(t + i) * 1.5
            cx, cy, r = x + dx * u, y + (dy + bob) * u, s * u
            path = QPainterPath()
            path.moveTo(cx, cy + r * 0.9)
            path.cubicTo(cx - r * 1.4, cy - r * 0.2, cx - r * 0.6, cy - r * 1.3, cx, cy - r * 0.4)
            path.cubicTo(cx + r * 0.6, cy - r * 1.3, cx + r * 1.4, cy - r * 0.2, cx, cy + r * 0.9)
            p.setPen(QPen(QColor("#8E1B3F"), 0.8 * u))
            p.setBrush(QColor("#FF4F7B"))
            p.drawPath(path)
    elif fx == "sparkles":
        for i, (dx, dy, s) in enumerate(((4, -4, 3.8), (14, 2, 2.6), (-8, -6, 2.4))):
            r = s * u * (0.8 + 0.25 * math.sin(t * 2 + i))
            cx, cy = x + dx * u, y + dy * u
            pts = []
            for j in range(8):
                a = j * math.pi / 4
                rr = r if j % 2 == 0 else r * 0.32
                pts.append(QPointF(cx + math.cos(a) * rr, cy + math.sin(a) * rr))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#FFD54A"))
            p.drawPolygon(QPolygonF(pts))
    elif fx == "anger":
        cx, cy, r = x + 10 * u, y - 1 * u, 4.2 * u
        p.setPen(QPen(QColor("#E53935"), 1.4 * u, Qt.SolidLine, Qt.RoundCap))
        for a in (0, 90, 180, 270):
            rad = math.radians(a + 45)
            ox, oy = math.cos(rad) * r * 0.45, math.sin(rad) * r * 0.45
            path = QPainterPath()
            path.moveTo(cx + ox * 2.0, cy + oy * 2.0)
            path.quadTo(cx + ox * 0.6, cy + oy * 0.6, cx + ox * 2.0 - oy * 1.2, cy + oy * 2.0 + ox * 1.2)
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
    elif fx == "shock":
        f = QFont()
        f.setBold(True)
        f.setPixelSize(int(12 * u))
        p.setFont(f)
        p.setPen(QPen(QColor("#E8762B")))
        p.drawText(QPointF(x + 9 * u, y + 1 * u), "!")
        p.setPen(QPen(QColor("#E8762B"), 0.9 * u, Qt.SolidLine, Qt.RoundCap))
        for a in (-40, -10, 20):
            rad = math.radians(a - 90)
            p.drawLine(QPointF(x + math.cos(rad) * 5 * u - 4 * u, y + math.sin(rad) * 5 * u),
                       QPointF(x + math.cos(rad) * 8 * u - 4 * u, y + math.sin(rad) * 8 * u))


# --------------------------------------------------------------------------- #
# drawing
# --------------------------------------------------------------------------- #
LIGHT = _norm((-0.45, 0.75, 0.6))
INK = QColor("#2A1A10")


def render(look: dict, mode: str = "idle", t: float = 0.0, k: float = 0.0, size: int = 128, **kw) -> QPixmap:
    """Draw a pose as a QPixmap (GUI thread only). See render_image."""
    return QPixmap.fromImage(render_image(look, mode, t, k, size, **kw))


def render_image(look: dict, mode: str = "idle", t: float = 0.0, k: float = 0.0, size: int = 128,
                 yaw: float = -0.8, pitch: float = 0.14, zoom: float = 1.0, outline: bool = True,
                 supersample: int = 2, mouth: float | None = None, mood: str | None = None) -> QImage:
    """Draw a pose. yaw turns the avatar (0 = side view facing right), pitch tilts the camera.
    Works in any thread (it only paints on a QImage)."""
    mesh = build(look, mode, t, k, mouth, mood)
    rot = _mm(_rx(pitch), _ry(yaw))
    ss = max(1, supersample)
    S = size * ss
    scale = S / 114.0 * zoom
    ox, oy = S / 2, S * 0.96
    if mode == "sleep":
        oy = S * 0.95
    polys = []
    for pts, n, col, shine, vis in mesh.faces:
        if vis is not None and _mv(rot, vis)[2] < 0.12:     # a detail on the far side of the head
            continue
        nn = _mv(rot, n)
        if nn[2] <= -0.02:                        # facing away
            continue
        tp = [_mv(rot, p) for p in pts]
        depth = sum(p[2] for p in tp) / len(tp)
        if vis is not None:
            depth += 4.0                          # details (eyes, nose, mouth) sit on top of their surface
        diff = nn[0] * LIGHT[0] + nn[1] * LIGHT[1] + nn[2] * LIGHT[2]
        # soft "wrapped" light: gentle from one face to the next, so the shapes look smooth and round
        f = 0.58 + 0.55 * ((diff * 0.5 + 0.5) ** 2)
        f -= (1.0 - nn[2]) ** 4 * 0.10             # a little darker at the edges
        c = _shade(col, f)
        if shine:
            hl = (LIGHT[0] * 0.5, LIGHT[1] * 0.5, LIGHT[2] * 0.5 + 0.5)
            sp = max(0.0, nn[0] * hl[0] + nn[1] * hl[1] + nn[2] * hl[2]) ** 20 * shine
            if sp > 0.01:
                c = QColor(min(255, int(c.red() + 230 * sp)), min(255, int(c.green() + 230 * sp)),
                           min(255, int(c.blue() + 230 * sp)))
        poly = QPolygonF([QPointF(ox + p[0] * scale, oy - p[1] * scale) for p in tp])
        polys.append((depth, poly, c))
    polys.sort(key=lambda x: x[0])

    img = QImage(S, S, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    # no antialiasing between faces (it shows the seams); the 2x drawing scaled down smooths the outline
    p.setRenderHint(QPainter.Antialiasing, ss == 1)
    for _, poly, c in polys:
        p.setPen(QPen(c, 1.1 * ss))
        p.setBrush(c)
        p.drawPolygon(poly)
    p.end()

    out = QImage(S, S, QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    q = QPainter(out)
    if outline:                                   # a soft ink line round the whole figure, like the 2D Primo
        sil = QImage(img)
        sp = QPainter(sil)
        sp.setCompositionMode(QPainter.CompositionMode_SourceIn)
        sp.fillRect(sil.rect(), QColor(mesh.outline))
        sp.end()
        w = (1.6 if mesh.outline == INK_DEFAULT else 1.1) * ss
        for i in range(12):
            a = 2 * math.pi * i / 12
            q.drawImage(QPointF(math.cos(a) * w, math.sin(a) * w), sil)
    q.drawImage(0, 0, img)
    if mesh.fx:                                   # hearts, sparkles, anger mark, "!"
        a = _mv(rot, mesh.anchor)
        _draw_fx(q, mesh.fx, ox + a[0] * scale, oy - a[1] * scale, scale, t)
    q.end()
    if ss > 1:
        out = out.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return out


def _zzz(img: QImage, k: int) -> QImage:
    img = QImage(img)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor("#5B8DEF"), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    s = img.width() / 128
    for i, (x, y, r) in enumerate(((88, 34, 6), (100, 20, 8))):
        if i > k:
            break
        x, y, r = x * s, y * s, r * s
        p.drawPolyline(QPolygonF([QPointF(x - r, y - r), QPointF(x + r, y - r), QPointF(x - r, y + r),
                                  QPointF(x + r, y + r)]))
    p.end()
    return img


# --------------------------------------------------------------------------- #
# frame sets for the pet (drawn once, then kept on disk)
# --------------------------------------------------------------------------- #
RUN_FRAMES = 10
RENDER_VERSION = 3           # bump when the drawing changes, so old cached frames are drawn again
SETS = ("run", "run_talk", "talk", "jump", "sleep", "wave", "angry", "laugh", "sad")


def make_frames(look: dict, size: int = 128) -> dict:
    """{'run', 'run_talk', 'talk', 'jump', 'sleep', 'wave'}: lists of QImages facing right. Any thread."""
    tau = 2 * math.pi
    r = lambda mode, t=0.0, k=0.0, **kw: render_image(look, mode, t, k, size, **kw)   # noqa: E731
    nap = r("sleep", 0.0)
    return {
        "run": [r("run", i / RUN_FRAMES * tau) for i in range(RUN_FRAMES)],
        # mouth opening and closing while running: he keeps running while he talks
        "run_talk": [r("run", i / RUN_FRAMES * tau, mouth=(0.85, 0.35, 0.0)[i % 3]) for i in range(RUN_FRAMES)],
        "talk": [r("talk", i / 8 * tau, (0.15, 0.7, 0.95, 0.5, 0.2, 0.8, 0.4, 0.0)[i]) for i in range(8)],
        "jump": [r("jump", 0.0, i / 11) for i in range(12)],
        "sleep": [_zzz(nap, 0), _zzz(nap, 1)],
        "wave": [r("wave", i / 10 * tau) for i in range(10)],
        # moods the app shows: angry when picked up, laughing it off, sulking (tampo) afterwards
        "angry": [r("idle", i / 8 * tau, mood="angry") for i in range(8)],
        "laugh": [r("talk", i / 8 * tau, (0.9, 0.5)[i % 2], mood="happy") for i in range(8)],
        "sad": [r("idle", i / 8 * tau, mood="sad") for i in range(8)],
    }


def _cache_file(look: dict, size: int) -> str:
    import hashlib
    import json
    from .store import config_dir
    key = hashlib.sha1(json.dumps([complete(look), size, RENDER_VERSION], sort_keys=True).encode()).hexdigest()[:16]
    d = os.path.join(config_dir(), "cache3d")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{key}.png")


def save_cache(look: dict, size: int, sets: dict) -> None:
    """All the frames in one PNG: a row per set, in SETS order."""
    cols = max(len(sets[n]) for n in SETS)
    sheet = QImage(cols * size, len(SETS) * size, QImage.Format_ARGB32_Premultiplied)
    sheet.fill(Qt.transparent)
    p = QPainter(sheet)
    for row, name in enumerate(SETS):
        for col, img in enumerate(sets[name]):
            p.drawImage(col * size, row * size, img)
    p.end()
    path = _cache_file(look, size)
    sheet.save(path + ".tmp.png")
    os.replace(path + ".tmp.png", path)
    d = os.path.dirname(path)                     # keep the newest few looks, drop the rest
    old = sorted((os.path.join(d, f) for f in os.listdir(d) if f.endswith(".png")), key=os.path.getmtime)
    for f in old[:-12]:
        try:
            os.remove(f)
        except OSError:
            pass


_COUNTS = {"run": RUN_FRAMES, "run_talk": RUN_FRAMES, "talk": 8, "jump": 12, "sleep": 2, "wave": 10, "angry": 8,
           "laugh": 8, "sad": 8}


def cached_frames(look: dict, size: int = 128) -> dict | None:
    """The frames from disk as QPixmaps (GUI thread), or None when they still have to be drawn."""
    path = _cache_file(look, size)
    if not os.path.exists(path):
        return None
    sheet = QPixmap(path)
    if sheet.isNull():
        return None
    return {name: [sheet.copy(c * size, row * size, size, size) for c in range(_COUNTS[name])]
            for row, name in enumerate(SETS)}


def draw_in_background(look: dict, done, size: int = 128) -> None:
    """Draw and cache the frames in a worker thread, then call done() (from that thread)."""
    import threading

    def work():
        try:
            save_cache(look, size, make_frames(look, size))
            done(True)
        except Exception:
            done(False)
    threading.Thread(target=work, daemon=True, name="capy-3d").start()
