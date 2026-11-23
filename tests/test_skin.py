"""The look: glass cards, soft lights and a gradient on the main button, in static/skin.css on top of app.css.

Expected: the look changes how things look and never what they mean. Blue still says "click", orange and red still say
how things stand, so the skin may not redefine those colours; it loads after app.css on every page, from its own address
only (the page allows nothing else), and it keeps still for anyone who asked for less motion. Under the mouse a control
may change its colour and its light, never its size or its place: a click draws the control again, and a control that
had grown or moved would jump back and glide out again under the pointer."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIN = (ROOT / "static" / "skin.css").read_text()


def test_every_page_loads_the_skin_after_the_base_styles(client):
    for path in ("/", "/bids", "/rules", "/nova", "/share"):
        html = client.get(path).get_data(as_text=True)
        assert html.index("app.css") < html.index("skin.css"), path
    assert client.get("/static/skin.css").status_code == 200


def test_the_skin_never_redefines_what_a_colour_means():
    declared = set(re.findall(r"(--[\w-]+)\s*:", SKIN))
    meaning = {"--blue", "--blue-deep", "--blue-soft", "--red", "--red-soft", "--orange", "--orange-soft", "--green",
               "--ink", "--ink-2", "--ink-3", "--paper", "--card", "--chip", "--line", "--line-2", "--line-3"}
    assert not declared & meaning, sorted(declared & meaning)


def test_the_skin_loads_nothing_from_outside():
    assert "@import" not in SKIN
    assert "http" not in SKIN
    assert re.findall(r"url\(([^)]*)\)", SKIN) == []


def test_the_skin_keeps_still_when_less_motion_is_asked_for():
    assert "prefers-reduced-motion: reduce" in SKIN
    assert "transform: none" in SKIN.split("prefers-reduced-motion: reduce")[1]


def test_no_control_grows_or_moves_under_the_mouse():
    hover_rules = re.findall(r"([^{}]*:hover[^{}]*)\{([^{}]*)\}", SKIN)
    assert hover_rules, "the skin still lights what the mouse is on"
    moving = [selector.strip() for selector, body in hover_rules if re.search(r"transform\s*:\s*(?!none)", body)]
    assert moving == [], moving
