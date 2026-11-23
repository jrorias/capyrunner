"""Dance showdowns between Primo and his friend Jeo OngBack.

Jeo runs in, the two take turns showing moves (there are 100 of them), then dance together and
somebody wins. For "Touch by Touch" there is no contest: Jeo dances a solo, then the two dance it together.
A showdown starts when a dance song is playing, every now and then on its own, or when you ask.

"Dance song" is decided from the words in the title and artist (nothing analyses the sound):
general dance words, plus the dance-challenge songs that are going round right now. That list
goes out of date; add your own under Settings -> Friend & dance.
"""
from __future__ import annotations

import random

# words that make any song a dance song
DANCE_WORDS = ("dance", "dancing", "sayaw", "budots", "tiktok mashup", "dance craze", "zumba", "choreograph",
               "showdown", "dj remix")

# (title, artist) - the artist may be '' when the title is unusual enough on its own.
# Dance trends reported for late 2026 (TikTok trend round-ups and Wikipedia; see the README).
TRENDING = (
    ("hawak mo ang beat", ""),          # the Philippine budots dance craze of 2026
    ("motion party", ""),
    ("dame hombro", ""),
    ("sey mami", ""),
    ("bby wow", "karol"),
    ("hideaway", "kiesza"),
    ("chanel", "tyla"),
    ("you spin me round", ""),          # the "chipmunks dance" mash-up is built on it
    ("feeling on my body", ""),
    ("m to the b", ""),
    ("boat", "trim"),
    ("pinoy ako", ""),                  # the Pinoy Big Brother theme, for Jeo
    ("touch by touch", ""),             # Joy's 1985 euro-disco hit, a dance challenge all over again
)

# The moves. Each one is put together from an arm pattern, a leg pattern and a body pattern
# (drawn by characters._dance_pose), so a new move is one more line here.
#   key | what they shout | arms legs body [fx] | tags
# tags: which styles use it (h hip-hop, d disco, b budots, k K-pop, c top-hat), s = the slow duet,
#       j = Jeo's show-off solo. No tag = any style.
_TABLE = """
wave       | Hands up! 🙌            | up bounce sway            | bk
point      | Point it! 🕺            | point wide sway           | d
shuffle    | Shuffle! 👟             | pump run bounce           | hb
spin       | Spin! 🌀                | tee bounce spin           | dkcj
headspin   | Headspin!! 🤯           | tee twist headspin        | hj
runningman | Running man! 🏃         | pump run groove           | h
moonwalk   | Moonwalk… 🌙            | snap moon slide           | dcj
floss      | Floss! 🦷               | floss wide hips           | k
dab        | Dab! 💥                 | dab wide pop              | h
robot      | Ro-bot. 🤖              | robot wide pop            | hk
worm       | The worm! 🪱            | up wide worm              | hj
backflip   | Backflip!! 🤸           | up hop flip               | hkj
cartwheel  | Cartwheel! 🎡           | tee wide cartwheel        | j
sprinkler  | Sprinkler! 💦           | sprinkler wide sway       | d
lasso      | Yee-haw lasso! 🤠       | lasso bounce bounce       |
stirpot    | Stir the pot! 🥣        | roll wide hips            | hd
raiseroof  | Raise the roof! 🏠      | roof bounce bounce        | h
fever      | Disco finger! 🪩        | disco wide hips           | d
hustle     | Do the hustle! ✨       | roll step sway            | d
swim       | The swim! 🏊            | swim bounce sway          | dc
twist      | Let's twist! 🌪️         | pump twist hips           | dc
charleston | Charleston! 🎷          | pump kick groove          | c
cancan     | Can-can! 💃             | hips cancan bounce        | c
tap        | Tap tap tap 🎩          | snap tap groove           | c
jazzhands  | Jazz hands! 🎭          | vogue wide shimmy         | c
pirouette  | Pirouette! 🩰           | twirl bounce spin         | ckj
heart      | Finger heart! 🫰        | heart bounce sway hearts  | ks
kpoint     | Point choreo! 🎤        | punch step pop            | k
bodyroll   | Body roll… 🌊           | hips wide roll hearts     | sk
hipsway    | Hip sway 💋             | head wide hips hearts     | s
touch      | Touch by touch! 💞      | touch step hips hearts    | s
smooth     | Smooth slide 😏         | slide wide roll hearts    | s
droplow    | Drop it low! 🔥         | head squat low            | shb
shimmy     | Shoulder shimmy! ✨     | shrug wide shimmy         | sdb
budots     | Budots! 😎              | shrug squat low           | b
budots2    | Budots hands! 🤙        | roll squat low            | b
wiggle     | Wiggle wiggle 🐛        | snap twist hips           | b
chicken    | Chicken dance! 🐔       | chicken bounce bounce     |
pharaoh    | Walk like a pharaoh 🏺  | egypt step pop            |
windmill   | Windmill arms! 🌬️       | windmill wide bounce      | h
jacks      | Jumping jacks! ⭐       | clap jack jump            |
clap       | Clap along! 👏          | clap step sway            |
fistpump   | Fist pump! ✊           | punch bounce jump         | h
headbang   | Headbang! 🤘            | punch wide bang           |
lean       | The lean! 🕴️            | snap wide lean            | hcj
bboy       | B-boy stance 😤         | cross wide groove         | h
guns       | Finger guns! 👉         | guns step sway            | d
pose       | Strike a pose! 📸       | vogue wide pop            | ks
armwave    | Arm wave 〰️             | ripple wide groove        | hk
highkick   | High kick! 🦵           | tee kick bounce           | k
bunnyhop   | Bunny hop! 🐇           | snap hop jump             |
crisscross | Criss-cross! ❌         | pump cross jump           | h
steptouch  | Step, touch 👣          | snap step sway            | cd
grapevine  | Grapevine! 🍇           | tee cross slide           |
pogo       | Pogo! 🦘                | up hop jump               |
superman   | Superman! 🦸            | roof kick lean            |
swing      | The happy swing! 😄     | floss step sway           | d
monkey     | The monkey! 🐒          | punch squat bang          | d
potato     | Mashed potato! 🥔       | chicken twist groove      | d
pony       | The pony! 🐴            | hips hop bounce           | d
hitchhike  | Hitch-hiker! 👍         | disco step sway           | d
bump       | The bump! 💥            | hips wide slide           | ds
busstop    | Bus stop! 🚌            | clap step slide           | d
handjive   | Hand jive! 🙌           | roll tap groove           | c
lindy      | Lindy hop! 🎺           | ripple kick jump          | c
waltz      | Waltz turn 🌹           | twirl step sway           | c
tango      | Tango! 🌹               | touch cross lean          | cs
salsa      | Salsa! 🌶️               | roll cross hips           | sc
chacha     | Cha-cha-cha! 💃         | snap cross hips           | c
limbo      | Limbo! 🎋               | tee squat lean            |
flex       | Flex! 💪                | punch wide pop            | b
otso       | Otso-otso! 8️⃣           | hips squat hips           | b
spaghetti  | Spaghetti arms! 🍝      | ripple twist hips         | b
hataw      | Hataw! ⚡               | windmill run jump         | b
starhands  | Star hands! 🌟          | lasso step sway           | bk
boogie     | Boogie! 🕺              | disco twist groove        | d
poplock    | Pop & lock! 🔒          | robot tap pop             | h
tutting    | Tutting! 📐             | egypt wide pop            | hk
stomp      | Stomp! 💢               | punch squat pop           | h
toprock    | Toprock! 🎧             | cross kick groove         | h
lowspin    | Low spin! 🌀            | tee squat spin            | hj
helicopter | Helicopter! 🚁          | windmill hop spin         | j
aerial     | Aerial! 🤸              | tee kick cartwheel        | j
frontflip  | Front flip! 🔁          | twirl hop fflip           | j
handstand  | Handstand! 🙃           | up kick stand             | hj
bellyslide | Belly slide! 🛝         | swim wide worm            | j
jump360    | 360 jump! 🌪️            | up hop spin               | kj
winkpoint  | Wink & point 😉         | guns wide hips hearts     | sk
blowkiss   | Blow a kiss 😘          | touch wide sway hearts    | s
catwalk    | Catwalk 🐈              | hips cross hips           | sk
hairflip   | Hair flip! 💁           | head wide bang hearts     | s
snakehips  | Snake hips 🐍           | ripple wide roll hearts   | s
closer     | Closer… closer 💃       | touch step roll hearts    | s
fanit      | Fan it! 🪭              | vogue step hips           | sc
lovewave   | Love wave 💗            | up wide hips hearts       | s
trend      | Trend hands! 📱         | swim wide pop             | kb
cute       | Cute pose! 🥰           | vogue hop bounce hearts   | k
tothesky   | To the sky! ☝️           | lasso wide jump           | kd
electric   | Electric slide! ⚡      | snap step slide           | dc
finish     | Big finish! 🎆          | roof jack jump            |
"""


def _parse(table: str) -> dict:
    out = {}
    for line in table.strip().splitlines():
        key, say, parts, tags = (c.strip() for c in line.split("|"))
        arms, legs, body, *fx = parts.split()
        out[key] = {"say": say, "arms": arms, "legs": legs, "body": body, "fx": fx[0] if fx else "", "tags": tags}
    return out


MOVES = _parse(_TABLE)                                 # 100 of them
BOB = {"say": "", "arms": "bob", "legs": "bounce", "body": "sway", "fx": "", "tags": ""}   # grooving while the other dances


def spec(move: str) -> dict:
    return MOVES.get(move) or BOB


ROUNDS = 2                # turns each before they dance together
TURN_SECS = 5.2           # one turn: two moves
BOTH_SECS = 10.5          # dancing together (as long as the song lasts when a dance song started it)
BOTH_MAX = 300.0
SOLO_SECS = 11.0          # Jeo's solo in a duet (Touch by Touch)
DUET_SECS = 17.5


def is_dance_song(title: str, artist: str = "", extra=()) -> bool:
    text = f" {title} {artist} ".lower()
    if not text.strip():
        return False
    if any(w in text for w in DANCE_WORDS):
        return True
    if any(str(w).strip().lower() in text for w in extra if str(w).strip()):
        return True
    return any(t in text and (not a or a in text) for t, a in TRENDING)


# A showdown has a style: the two change into its outfit (poof!) and dance its moves.
# words = what in a song's title / artist picks this style; otherwise the style is drawn at random.
# tag   = which moves belong to it (see the table above). duet = no contest: Jeo dances a solo,
#         then Primo joins him for a slow one together.
STYLES = {
    "touch": {"label": "Touch by Touch", "icon": "💞", "primo": "#D81B60", "jeo": "#6A1B9A", "tag": "s",
              "duet": True, "fps": 9, "words": ("touch by touch",)},
    "hiphop": {"label": "Hip-hop battle", "icon": "🧢", "primo": "#B5282E", "jeo": "#1E1E24", "tag": "h",
               "words": ("hip hop", "hip-hop", "rap", "trap", "phonk", "boat", "m to the b", "motion party")},
    "disco": {"label": "Disco fever", "icon": "🪩", "primo": "#7B2FBE", "jeo": "#E0A200", "tag": "d",
              "words": ("disco", "dancing queen", "you spin me", "hideaway", "funk", "retro", "80s")},
    "budots": {"label": "Budots showdown", "icon": "😎", "primo": "#2F9E44", "jeo": "#F26A1B", "tag": "b",
               "words": ("budots", "hawak mo ang beat", "sayaw", "tiktok mashup", "pinoy", "dame hombro")},
    "kpop": {"label": "K-pop stage", "icon": "🎤", "primo": "#F29BC1", "jeo": "#8FC8F2", "tag": "k",
             "words": ("k-pop", "kpop", "bts", "blackpink", "twice", "newjeans", "seventeen", "stray kids")},
    "classy": {"label": "Top-hat tap-off", "icon": "🎩", "primo": "#22222A", "jeo": "#5B1F2E", "tag": "c",
               "words": ("swing", "jazz", "tango", "waltz", "ballroom", "cha cha")},
}


# the mood of the song (see activity.guess_mood) -> the showdown styles that suit it.
# Only these moods start a dance by themselves; sad songs get the quiet listening pose instead.
MOOD_DANCES = {
    "hype": ("hiphop", "budots", "kpop"),
    "happy": ("disco", "kpop", "budots"),
    "love": ("touch", "classy"),
}


def pick_style(text: str = "", last: str = "", mood: str = "") -> str:
    """The style a song's words ask for, else one that fits its mood, else any (not the last one again)."""
    text = f" {text} ".lower()
    for name, st in STYLES.items():
        if text.strip() and any(w in text for w in st["words"]):
            return name
    fits = [n for n in MOOD_DANCES.get(mood, ()) if n != last]
    return random.choice(fits or [n for n in STYLES if n != last])


def pool(style: str, solo: bool = False) -> list[str]:
    """The moves of a style: its own and the ones that fit anywhere. solo = Jeo's show-off moves.
    The slow duet keeps to its own moves."""
    tag = "j" if solo else STYLES.get(style, {}).get("tag", "")
    own = [m for m, v in MOVES.items() if tag and tag in v["tags"]]
    if solo or STYLES.get(style, {}).get("duet"):
        return own
    return own + [m for m, v in MOVES.items() if not v["tags"]]


def style_move(style: str, used=(), solo: bool = False) -> str:
    """A move for this style that has not been danced yet in this showdown (used)."""
    moves = pool(style, solo) or list(MOVES)
    fresh = [m for m in moves if m not in used]
    if not fresh:
        last = list(used)[-1:] if used else []
        fresh = [m for m in moves if m not in last] or moves
    return random.choice(fresh)
