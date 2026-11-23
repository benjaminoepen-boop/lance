"""LN08: the share page shows in a short video how the button gets the rank lists from the platform to Lance.

Expected: /share plays the video from Lance itself, with a picture before it starts and English captions, and the
files come with the types a browser insists on (with nosniff on, a caption file not sent as text/vtt is ignored)."""
import re


def test_the_share_page_shows_the_video_with_captions(client):
    html = client.get("/share").get_data(as_text=True)
    video = re.search(r"<video.*?</video>", html, re.S).group(0)
    assert 'src="/static/video/share-howto.mp4" type="video/mp4"' in video
    assert 'poster="/static/video/share-howto-poster.jpg"' in video
    assert re.search(r'<track kind="captions" src="/static/video/share-howto.vtt" srclang="en"', video)


def test_the_video_files_come_with_their_types(client):
    assert client.get("/static/video/share-howto.mp4").mimetype == "video/mp4"
    captions = client.get("/static/video/share-howto.vtt")
    assert captions.mimetype == "text/vtt"
    assert captions.get_data(as_text=True).startswith("WEBVTT")
    assert client.get("/static/video/share-howto-poster.jpg").mimetype == "image/jpeg"

