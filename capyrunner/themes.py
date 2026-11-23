"""Weekday adventures: every working day Primo's lap around the screen is a different trip.

The five days tell one story, "Primo and the fiesta star":
  Monday     training day (the classic rope lap)
  Tuesday    hiking up the mountain to spot the brightest star
  Wednesday  rocket up to space to catch it, parachute back down
  Thursday   the star fell out over the jungle: treasure hunt
  Friday     fiesta: the star goes into the lantern, tacos for everyone

A theme only changes how the same lap looks and sounds: the outfit, the rope, and what
happens on the way up (right edge), along the top, and on the way down (left edge).
"""
from __future__ import annotations

from datetime import date

THEMES: dict[str, dict] = {
    "classic": {
        "label": "Training day (classic lap)", "icon": "🏃",
        "outfit": "", "jacket": None, "rope": "rope",
        "climb": "rope", "top": "sneak", "descend": "rope", "falls": True,
        "story": "🏃 Training day! Friday is the fiesta and the lantern needs a real star… I have to get fit first.",
        "cheers": ["Training hard for the big trip! 🏃", "Tomorrow: the mountain 🏔️"],
    },
    "hike": {
        "label": "Mountain hike", "icon": "🏔️",
        "outfit": "hike", "jacket": "#C8442E", "rope": "climb",
        "climb": "rope", "top": "walk", "descend": "rope", "falls": True,
        "story": "🏔️ Hiking day! From the summit I can find the brightest star for the fiesta lantern.",
        "arrive": "Clip in… up we go! 🧗",
        "top_say": "What a view from the ridge! 🏔️",
        "think": "🚩 Summit! I see it: that star, right there. I'll need a rocket…",
        "land": "Back at base camp. Tomorrow: space! 🚀",
        "cheers": ["One step at a time, like a mountain 🥾", "Trail mix break? 🥜", "The summit is closer than it looks 🏔️"],
    },
    "space": {
        "label": "Space mission", "icon": "🚀",
        "outfit": "space", "jacket": "#F2F4F8", "rope": "none",
        "climb": "rocket", "top": "float", "descend": "chute", "falls": False,
        "story": "🚀 Launch day! Suit on. I'm flying up to catch the star I saw from the mountain.",
        "count": ["Systems check… ✅", "3…", "2…", "1…", "Lift-off! 🚀"],
        "top_say": "Zero gravity! Wheee… 🌌",
        "think": "⭐ Got the star! And look, home, way down there 🌍",
        "land": "Touchdown! 🪂 …wait. The star fell out over the jungle!",
        "cheers": ["Mission control says: you are go! 🚀", "Houston, we have no problem 👨‍🚀", "Aim for the stars ⭐"],
    },
    "jungle": {
        "label": "Jungle treasure hunt", "icon": "🌴",
        "outfit": "jungle", "jacket": "#B8975A", "rope": "vine",
        "climb": "rope", "top": "sneak", "descend": "rope", "falls": True,
        "story": "🌴 Jungle day! The star dropped somewhere in these trees. Treasure hunt!",
        "arrive": "A vine! Up into the canopy 🌿",
        "top_say": "Shh… a jaguar is sleeping 🐆",
        "think": "✨ Found it! The star, safe in a nest.",
        "land": "Star in the bag. Tomorrow we celebrate! 🎉",
        "cheers": ["X marks the spot 🗺️", "Every explorer needs water 💧", "Treasure is hiding in your to-do list 💎"],
    },
    "fiesta": {
        "label": "Fiesta Friday", "icon": "🎉",
        "outfit": "fiesta", "jacket": None, "rope": "bunting",
        "climb": "rope", "top": "walk", "descend": "rope", "falls": True,
        "story": "🎉 Fiesta Friday! Mountain, space, jungle… the star is home. Let's hang the lantern!",
        "arrive": "Banderitas going up! 🎏",
        "top_say": "Almost there… fiesta, fiesta! 🎶",
        "think": "🌟 The lantern is up. Look at it shine!",
        "land": "Done! Tacos for everyone 🌮",
        "cheers": ["It's Friday! Taco time soon 🌮", "What a week: mountain, space, jungle ⭐", "Finish strong, then fiesta 🎉"],
    },
}

ORDER = ("classic", "hike", "space", "jungle", "fiesta")
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
DEFAULT_WEEK = ["classic", "hike", "space", "jungle", "fiesta", "classic", "classic"]


def current(settings: dict, today: date | None = None) -> str:
    """The theme to wear right now: a fixed choice, or the one planned for this weekday ('auto')."""
    choice = settings.get("day_theme", "auto")
    if choice in THEMES:
        return choice
    week = settings.get("week_themes") or DEFAULT_WEEK
    d = (today or date.today()).weekday()
    name = week[d] if d < len(week) else "classic"
    return name if name in THEMES else "classic"


def get(name: str) -> dict:
    return THEMES.get(name) or THEMES["classic"]
