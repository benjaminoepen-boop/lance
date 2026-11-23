"""The logo: a sealed bid, the same blue envelope in the top bar, in the browser tab and on a home screen.

Expected: every page draws the envelope in its top bar itself, the tab shows the same envelope, an iPhone gets
a picture of 180 x 180 pixels (it ignores SVG icons) and an installed app gets 192 and 512 pixels next to the SVG."""
import json
import re

# the flap of the envelope, as it stands in the logo the team chose
FLAP = "M4.101 4.101A14 14 0 0 1 14 0H50A14 14 0 0 1 59.899 4.101L32 32Z"


def size_of_png(response):
    """Width and height, from the header every PNG file starts with."""
    assert response.status_code == 200
    data = response.get_data()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def test_every_page_draws_the_envelope_in_its_top_bar(client):
    for path in ("/", "/bids", "/nova", "/rules", "/share"):
        html = client.get(path).get_data(as_text=True)
        brand = re.search(r'<a class="brand".*?</a>', html, re.S).group(0)
        assert FLAP in brand and 'class="seal"' in brand, path


def test_the_tab_shows_the_same_envelope(client):
    html = client.get("/").get_data(as_text=True)
    assert '<link rel="icon" href="/static/icon.svg" type="image/svg+xml">' in html
    assert FLAP in client.get("/static/icon.svg").get_data(as_text=True)


def test_an_iphone_gets_a_picture_of_180_pixels(client):
    html = client.get("/").get_data(as_text=True)
    picture = re.search(r'<link rel="apple-touch-icon" href="([^"]+\.png)"', html)
    assert picture, "an iPhone ignores an SVG here"
    assert size_of_png(client.get(picture.group(1))) == (180, 180)


def test_an_installed_app_gets_pictures_of_192_and_512_pixels_next_to_the_svg(client):
    icons = json.loads(client.get("/static/manifest.json").get_data())["icons"]
    pictures = {icon["sizes"]: size_of_png(client.get(icon["src"])) for icon in icons if icon["type"] == "image/png"}
    assert pictures == {"192x192": (192, 192), "512x512": (512, 512)}
    svg = [icon["src"] for icon in icons if icon["type"] == "image/svg+xml"]
    assert svg and FLAP in client.get(svg[0]).get_data(as_text=True)
