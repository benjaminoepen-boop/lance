"""Build a static copy of Lance that works from a private link, without a server.

The pages are the real ones, rendered by the real app. Only the rules run in the browser here (lance-local.js),
and preview/check_parity.py compares those with logic.py. This folder is not part of the app itself.

Run:  uv run python preview/build_preview.py preview/out
"""
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.environ["LANCE_DB"] = os.path.join(tempfile.mkdtemp(), "preview.db")

import app as lance   # noqa: E402
import db             # noqa: E402
import logic          # noqa: E402

BANNER = ('<div style="background:var(--orange-soft);color:var(--orange);padding:7px 14px;font-size:13px;'
          'border-radius:8px;font-weight:500">Preview. Your plan stays in this browser. '
          'Ratings, shared rank lists and the calendar file need the full app.</div>')


def data_file():
    offerings = db.load_offerings()
    kinds = {programme: db.load_programme_kinds(programme) for programme in db.load_programmes()}
    meetings = {key: [dict(m) for m in rows] for key, rows in logic.all_meetings().items()}
    sessions = {key: [{k: s[k] for k in ("date", "start", "end", "room", "note")} for s in rows]
                for key, rows in logic.all_sessions().items()}
    exams = {f"{code}-{term}": rows for (code, term), rows in logic.all_exams().items()}
    return {
        "offerings": offerings, "sections": db.load_sections(), "meetings": meetings, "sessions": sessions, "exams": exams,
        "kinds": kinds, "cutoffs": db.load_cutoffs(), "histograms": db.load_histograms(), "calendar": db.load_calendar(),
        "example": [list(row) for row in logic.EXAMPLE_PLAN],
    }


def relative_links(html):
    """The app's addresses become the files of the static copy."""
    html = html.replace('href="/static/', 'href="').replace('src="/static/', 'src="')
    html = re.sub(r'href="/course/([^"#]+)#?[^"]*"', r'href="course.html#\1"', html)
    for address, page in (('/bids', 'bids.html'), ('/rules', 'rules.html'), ('/share', 'share.html'), ('/', 'index.html')):
        html = html.replace(f'href="{address}"', f'href="{page}"')
    html = re.sub(r'<link rel="manifest"[^>]*>', '', html)
    html = re.sub(r'<link rel="(icon|apple-touch-icon)"[^>]*>', '', html)
    return html


def with_preview_script(html):
    """Load the browser copy of the rules before anything else, and say that this is a preview."""
    html = html.replace('<script src="common.js"></script>', '<script src="lance-local.js"></script>\n<script src="common.js"></script>')
    html = html.replace('<main class="main" id="main">', f'<main class="main" id="main">\n{BANNER}')
    return html


def page_html(client, address):
    return with_preview_script(relative_links(client.get(address).get_data(as_text=True)))


def main_block(html):
    start = html.index('<main class="main" id="main">') + len('<main class="main" id="main">')
    end = html.index('</main>')
    return html[start:end]


def main(out_dir):
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(os.path.join(out_dir, "fonts"))
    client = lance.app.test_client()

    pages = {"index.html": "/", "bids.html": "/bids", "rules.html": "/rules", "share.html": "/share"}
    for name, address in pages.items():
        html = page_html(client, address)
        # the plan link and the calendar file only exist in the full app
        html = re.sub(r'<a class="btn small" href="/plan\.ics"[^>]*>.*?</a>', '', html, flags=re.S)
        html = re.sub(r'<button type="button" class="btn small" id="copy-link".*?</button>', '<span id="copy-link" hidden></span>', html, flags=re.S)
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as file:
            file.write(html)

    # one shell for every course sheet; the sheets themselves are rendered once and kept in one file
    sheets = {}
    for offering in db.load_offerings():
        body = main_block(relative_links(client.get("/course/" + offering["id"]).get_data(as_text=True)))
        sheets[offering["id"]] = body
    with open(os.path.join(out_dir, "courses.json"), "w", encoding="utf-8") as file:
        json.dump(sheets, file, ensure_ascii=False)
    shell = client.get("/course/2477-S1").get_data(as_text=True)
    start = shell.index('<main class="main" id="main">') + len('<main class="main" id="main">')
    end = shell.index('</main>')
    shell = shell[:start] + '\n<div id="sheet-slot" style="display:contents"></div>\n' + shell[end:]
    shell = shell.replace('<title>Lance · Introduction to Programming</title>', '<title>Lance · Course</title>')
    shell = with_preview_script(relative_links(shell))
    shell = shell.replace('<script src="course.js"></script>', '<script src="course-preview.js"></script>')
    with open(os.path.join(out_dir, "course.html"), "w", encoding="utf-8") as file:
        file.write(shell)

    with open(os.path.join(out_dir, "data.json"), "w", encoding="utf-8") as file:
        json.dump(data_file(), file, ensure_ascii=False)

    for name in ("app.css", "common.js", "planner.js", "bids.js", "rules.js", "share.js"):
        shutil.copy(os.path.join(ROOT, "static", name), os.path.join(out_dir, name))
    for name in os.listdir(os.path.join(ROOT, "static", "fonts")):
        shutil.copy(os.path.join(ROOT, "static", "fonts", name), os.path.join(out_dir, "fonts", name))
    shutil.copy(os.path.join(HERE, "lance-local.js"), os.path.join(out_dir, "lance-local.js"))
    shutil.copy(os.path.join(HERE, "course-preview.js"), os.path.join(out_dir, "course-preview.js"))

    # the scripts link to app addresses too
    for name in ("planner.js", "bids.js"):
        path = os.path.join(out_dir, name)
        with open(path, encoding="utf-8") as file:
            text = file.read()
        text = text.replace("`/course/${course.id}`", "`course.html#${course.id}`")
        text = text.replace("`/course/${block.offering_id}`", "`course.html#${block.offering_id}`")
        text = text.replace("`/course/${first.offering_id}`", "`course.html#${first.offering_id}`")
        text = text.replace('href: "/share"', 'href: "share.html"').replace('href: "/"', 'href: "index.html"')
        with open(path, "w", encoding="utf-8") as file:
            file.write(text)

    # the main page of an artifact is published without its document skeleton
    with open(os.path.join(out_dir, "index.html"), encoding="utf-8") as file:
        index = file.read()
    head = re.search(r"<head>(.*?)</head>", index, re.S).group(1)
    body = re.search(r"<body[^>]*>(.*)</body>", index, re.S).group(1)
    head = re.sub(r'<meta charset[^>]*>|<meta name="viewport"[^>]*>|<meta name="theme-color"[^>]*>', '', head)
    head = head.replace("<title>Lance · Planner</title>", "<title>Lance Bidding Planner</title>")
    with open(os.path.join(out_dir, "lance-preview.html"), "w", encoding="utf-8") as file:
        file.write(head.strip() + '\n<div data-page="planner" style="display:contents">' + body + "</div>\n")
    total = sum(os.path.getsize(os.path.join(folder, name)) for folder, _, names in os.walk(out_dir) for name in names)
    print(f"preview built in {out_dir}: {total // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1])
