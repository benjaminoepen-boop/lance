"""The screens of Lance. Rules live in logic.py, storage in db.py; this file only connects them to the browser.

Run:  uv run flask --app app run --port 8770
"""
import json
import os
from datetime import date
from urllib.parse import quote

from flask import Flask, Response, abort, jsonify, make_response, redirect, render_template, request, url_for

import db
import logic

app = Flask(__name__)
# A real export is a few hundred KB at most. A larger body is refused with 413 before it is read.
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024
db.init_db()

COOKIE = "lance_plan"
ONE_YEAR = 60 * 60 * 24 * 365
HERE = os.path.dirname(os.path.abspath(__file__))


# ---------- who is this? A plan needs no account: a random id in a cookie is all there is. ----------

def current_plan():
    """Return this visitor's plan and whether it was just created."""
    plan_id = request.cookies.get(COOKIE, "")
    plan = logic.load_plan(plan_id) if plan_id else None
    if plan is not None:
        return plan, False
    return logic.load_plan(logic.default_plan_id()), True


def remember(response, plan):
    response.set_cookie(COOKIE, plan["id"], max_age=ONE_YEAR, httponly=True, samesite="Lax")
    return response


def semester_option(name, today=None):
    """What the semester menu says. A round that is over still plans, as practice, so it says "practice":
    "closed" read as if the semester could not be chosen at all (first-time user test, 10 Nov)."""
    round_ = logic.round_of(name, today)
    if round_ is not None and round_["status"] == "closed":
        return name + " · practice"
    return logic.semester_label(name, today)


def page(template, plan, is_new, **values):
    """Render a page and keep the plan cookie alive."""
    state = logic.state_of(plan)
    semesters = [(name, semester_option(name)) for name in ("Fall", "Spring")]
    response = make_response(render_template(template, plan=plan, state=state, programmes=db.load_programmes(), semesters=semesters, **values))
    return remember(response, plan)


@app.after_request
def safe_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; base-uri 'self'; form-action 'self'")
    return response


# ---------- pages ----------

@app.route("/")
def planner():
    plan, is_new = current_plan()
    return page("planner.html", plan, is_new, active="planner")


@app.route("/bids")
def bids():
    plan, is_new = current_plan()
    return page("bids.html", plan, is_new, active="bids", platform_list=logic.platform_list(plan))


@app.route("/course/<offering_id>")
def course(offering_id):
    """A link to a course: the planner with that course already open."""
    plan, is_new = current_plan()
    if logic.course_page(offering_id, plan) is None:
        abort(404)
    return page("planner.html", plan, is_new, active="planner", open_course=offering_id)


@app.route("/nova")
def nova():
    plan, is_new = current_plan()
    return page("nova.html", plan, is_new, active="nova", platform_list=logic.platform_list(plan))


@app.route("/rules")
def rules():
    plan, is_new = current_plan()
    return page("rules.html", plan, is_new, active="rules", calendar=calendar_rows(), today=date.today().isoformat())


@app.route("/share")
def share():
    plan, is_new = current_plan()
    with open(os.path.join(HERE, "static", "share-bookmarklet.js"), encoding="utf-8") as file:
        bookmarklet = "javascript:" + quote(file.read().strip(), safe="(){}[];,.=&|!<>+*/:'\"-_?%~")
    return page("share.html", plan, is_new, active="share", coverage=logic.coverage(), bookmarklet=bookmarklet)


@app.route("/p/<plan_id>")
def open_plan(plan_id):
    """The link to continue a plan on another device."""
    plan = db.load_plan(plan_id)
    if plan is None:
        abort(404)
    return remember(redirect(url_for("planner")), plan)


@app.route("/plan.ics")
def calendar_download():
    plan, _ = current_plan()
    response = Response(logic.calendar_file(plan), mimetype="text/calendar")
    response.headers["Content-Disposition"] = "attachment; filename=lance-plan.ics"
    return remember(response, plan)


def calendar_rows():
    rows = []
    for row in db.load_calendar():
        row = dict(row)
        row["first_label"] = logic.day_label(row["first_day"])
        row["last_label"] = logic.day_label(row["last_day"])
        row["is_window"] = "bidding" in row["key"] or "add-drop" in row["key"]
        rows.append(row)
    return rows


# ---------- what the pages ask for while you work ----------

def answer(plan, error=None, **more):
    """Every change answers with the fresh state, so the page never has to guess.
    The plan is read again first: a change to the mandatory courses changes the estimated points."""
    plan = logic.load_plan(plan["id"])
    body = {"error": error, "state": logic.state_of(plan), **more}
    return remember(jsonify(body), plan)


def payload():
    """The JSON a page sent. Refusing anything else keeps other websites from posting here."""
    try:
        data = request.get_json(silent=True)
    except RecursionError:      # brackets nested thousands deep: no page sends that
        data = None
    if not isinstance(data, dict):
        abort(415)
    return data


@app.route("/api/state")
def api_state():
    plan, _ = current_plan()
    return answer(plan)


@app.route("/api/catalogue")
def api_catalogue():
    plan, _ = current_plan()
    return remember(jsonify(logic.catalogue(plan)), plan)


@app.route("/api/add", methods=["POST"])
def api_add():
    plan, _ = current_plan()
    data = payload()
    error = logic.add_to_plan(plan, section_id=data.get("section_id"), offering_id=data.get("offering_id"), list_name=data.get("list"))
    return answer(plan, error)


@app.route("/api/remove", methods=["POST"])
def api_remove():
    """One section by its entry, or a whole course. A whole course answers with what undo needs."""
    plan, _ = current_plan()
    data = payload()
    if data.get("offering_id"):
        removed, error = logic.remove_course(plan, data["offering_id"])
        return answer(plan, error, removed=removed)
    return answer(plan, logic.remove_from_plan(plan, data.get("item_id")))


@app.route("/api/restore", methods=["POST"])
def api_restore():
    plan, _ = current_plan()
    return answer(plan, logic.restore_items(plan, payload().get("rows")))


@app.route("/api/switch", methods=["POST"])
def api_switch():
    plan, _ = current_plan()
    return answer(plan, logic.switch_section(plan, payload().get("section_id")))


@app.route("/api/start-over", methods=["POST"])
def api_start_over():
    """Empties the semester on show and answers with what undo needs, like removing one course."""
    plan, _ = current_plan()
    return answer(plan, removed=logic.start_over(plan))


@app.route("/api/sheet/<offering_id>")
def api_sheet(offering_id):
    """The left column when a course is open: rendered here, so that it needs no JavaScript of its own."""
    plan, _ = current_plan()
    sheet = logic.course_page(offering_id, plan)
    if sheet is None:
        abort(404)
    return render_template("_sheet.html", sheet=sheet, plan=plan)


@app.route("/api/bid", methods=["POST"])
def api_bid():
    plan, _ = current_plan()
    data = payload()
    if data.get("offering_id"):
        return answer(plan, logic.set_course_bid(plan, data["offering_id"], data.get("bid")))
    return answer(plan, logic.set_bid(plan, data.get("item_id"), data.get("bid")))


@app.route("/api/move", methods=["POST"])
def api_move():
    plan, _ = current_plan()
    data = payload()
    error = logic.move_item(plan, data.get("item_id"), list_name=data.get("list"), direction=data.get("direction"))
    return answer(plan, error)


@app.route("/api/settings", methods=["POST"])
def api_settings():
    plan, _ = current_plan()
    data = payload()
    error = logic.update_settings(plan, data.get("programme", plan["programme"]), data.get("semester", plan["semester"]),
                                  data.get("points"), bool(data.get("has_bonus", plan["has_bonus"])))
    return answer(plan, error)


@app.route("/api/example", methods=["POST"])
def api_example():
    plan, _ = current_plan()
    error = logic.load_example(plan)
    return answer(plan, error)


@app.route("/api/share", methods=["POST"])
def api_share():
    """A rank-list export. The rules keep totals only; the rows themselves are never written anywhere."""
    try:
        data = request.get_json(silent=True)
        text = data.get("export") if isinstance(data, dict) else None
        export = json.loads(text) if isinstance(text, str) else None
    except (ValueError, RecursionError):     # not JSON at all, or brackets nested thousands deep
        export = None
    if export is None:
        return jsonify({"error": "This does not look like what the button copies.", "stored": 0}), 400
    stored, error = logic.share_rank_lists(export)
    if error:
        return jsonify({"error": error, "stored": 0}), 400
    return jsonify({"error": None, "stored": stored, "coverage": logic.coverage()})


@app.errorhandler(logic.Malformed)
def malformed(error):
    """A value of the wrong kind, like a list where an id belongs: refused with a short sentence before any rule ran."""
    return jsonify({"error": str(error)}), 400


@app.errorhandler(415)
def not_json(_):
    return jsonify({"error": "Lance takes only what its pages send: a JSON object."}), 415


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "This is too large: Lance takes at most 512 KB at once.", "stored": 0}), 413


@app.errorhandler(404)
def not_found(_):
    return '<p style="font-family:sans-serif;margin:40px">This page does not exist. <a href="/">Back to Lance</a></p>', 404
