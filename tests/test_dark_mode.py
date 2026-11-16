"""The dark colour scheme: a phone or laptop set to dark gets a dark Lance, and the text stays readable.

Expected: every colour in :root has a dark value, ink is readable on every surface and on every course
colour (the same bar as the light scheme), and the page tells the browser that it supports both schemes."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static" / "app.css").read_text()
HEX = re.compile(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})\b")


def block(opening):
    """The text between the braces of the rule that starts with `opening`."""
    start = CSS.index(opening)
    depth, i = 0, CSS.index("{", start)
    first = i
    while True:
        depth += CSS[i] == "{"
        depth -= CSS[i] == "}"
        if depth == 0:
            return CSS[first + 1:i]
        i += 1


def colours(text):
    return {name: value.lower() for name, value in HEX.findall(text)}


def luminance(value):
    channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


LIGHT = colours(block(":root {"))
DARK = colours(block("@media (prefers-color-scheme: dark)")) if "prefers-color-scheme: dark" in CSS else {}


def test_every_colour_has_a_dark_value():
    missing = sorted(name for name in LIGHT if name not in DARK)
    assert not missing, f"no dark value for {missing}"


def test_text_is_readable_on_every_surface():
    for surface in ("--paper", "--card", "--chip"):
        assert contrast(DARK["--ink"], DARK[surface]) >= 7, surface
        assert contrast(DARK["--ink-2"], DARK[surface]) >= 7, surface
        assert contrast(DARK["--ink-3"], DARK[surface]) >= 4.5, surface


def test_ink_is_readable_on_every_course_colour():
    hues = ("olive", "plum", "teal", "violet", "forest", "mauve", "jade", "petrol")
    names = [f"--{hue}-soft" for hue in hues]
    assert all(name in LIGHT for name in names)
    for name in names:
        assert contrast(DARK["--ink"], DARK[name]) >= 7, name
        assert contrast(DARK["--ink-2"], DARK[name]) >= 4.5, name


def test_status_colours_are_readable_on_their_soft_background():
    for strong, soft in (("--red", "--red-soft"), ("--orange", "--orange-soft")):
        assert contrast(DARK[strong], DARK[soft]) >= 4.5, strong


def test_blue_is_readable_as_text_and_under_the_words_of_a_button():
    assert contrast(DARK["--blue"], DARK["--card"]) >= 4.5
    assert contrast(DARK["--blue-deep"], DARK["--card"]) >= 4.5
    assert contrast(DARK["--on-blue"], DARK["--blue"]) >= 4.5


def test_the_page_says_it_supports_both_schemes(client):
    html = client.get("/").get_data(as_text=True)
    assert 'name="color-scheme" content="light dark"' in html
    assert html.count('name="theme-color"') == 2
