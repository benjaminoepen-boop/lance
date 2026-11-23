"""Choosing alternates in the week: a plus puts a course on the alternate list, and the week can show where it lies.

Expected, from the brief: LN R13 stays as it is. The week is the first section of each course on the mandatory and
primary lists; an alternate is checked against those two lists and says what it meets in its own row. The alternate
list holds no points (LN R6) and no ECTS (LN R8). New is only what gets drawn: the state marks the first section of
each course on the alternate list, with its days and hours, so that the page can draw it beside the week's own blocks.

Real timetable used here:
Family Business 2416-T1: TXA Wed 08:00 and Fri 12:30.
Fundamentals on Environment and Sustainability 2652-S1: TXA Wed 15:30-18:30.
Impact Investments 2277-T2: TXA Wed 15:30-18:30, TXB Thu 15:30-18:30.
Advanced Strategy 2459-S1: TXC (mandatory for Management).
"""


def add(client, **body):
    answer = client.post("/api/add", json=body).get_json()
    assert answer["error"] is None, answer["error"]
    return answer["state"]


def rows_of(state):
    return {item["section_id"]: item for item in state["items"]}


# ---------- a plus for the alternate list ----------

def test_a_plus_for_the_alternate_list_puts_the_course_there(client):
    state = add(client, offering_id="2416-T1", list="alternate")
    assert [(item["offering_id"], item["section_id"], item["list"]) for item in state["items"]] == [("2416-T1", "2416-T1-TXA", "alternate")]


def test_an_alternate_holds_no_points_and_no_ects(client):
    # LN R6: the alternate list takes nothing while bidding. LN R8: it does not count for the ECTS.
    state = add(client, offering_id="2416-T1", list="alternate")
    client.post("/api/bid", json={"offering_id": "2416-T1", "bid": 40})
    state = client.get("/api/state").get_json()["state"]
    assert state["items"][0]["bid"] == 40
    assert state["reserved"] == 0
    assert state["ects"]["total"] == 0


def test_the_left_arrow_takes_an_alternate_back(client):
    # LN R19: adding is one change, whichever list it goes to
    add(client, offering_id="2416-T1", list="alternate")
    state = client.post("/api/undo", json={}).get_json()["state"]
    assert state["items"] == []


# ---------- what the week needs to draw an alternate ----------

def test_the_state_says_where_an_alternate_lies_in_the_week(client):
    item = add(client, offering_id="2416-T1", list="alternate")["items"][0]
    assert item["name"] == "Family Business"
    assert item["section"] == "TXA"
    assert item["term"] == "T1"   # which half of the semester its blocks belong to
    assert [(m["day"], m["start"], m["end"], m["room"]) for m in item["meetings"]] == [("Wed", "08:00", "09:30", "D.-1.10"), ("Fri", "12:30", "14:00", "D.-1.05")]
    assert item["in_alternate_week"] is True


def test_an_alternate_is_shown_but_stays_out_of_the_week(client):
    # LN R13: the week is the mandatory and the primary list. Fundamentals meets Impact Investments TXA on Wednesday 15:30:
    # that is no clash of the week, the alternate says it in its own row.
    add(client, section_id="2459-S1-TXC")
    add(client, section_id="2277-T2-TXA")
    state = add(client, offering_id="2652-S1", list="alternate")
    rows = rows_of(state)
    assert [rows[section]["in_week"] for section in ("2459-S1-TXC", "2277-T2-TXA", "2652-S1-TXA")] == [True, True, False]
    assert [rows[section]["in_alternate_week"] for section in ("2459-S1-TXC", "2277-T2-TXA", "2652-S1-TXA")] == [False, False, True]
    assert state["clashes"] == []
    assert [note["text"] for note in rows["2652-S1-TXA"]["conflicts"]] == ["Clashes with Impact Investments TXA"]


def test_only_the_first_section_of_an_alternate_course_is_shown(client):
    # as in the week: one block per course. A further section of an alternate course is a backup and joins its list.
    add(client, section_id="2277-T2-TXB", list="alternate")
    rows = rows_of(add(client, section_id="2277-T2-TXA"))
    assert rows["2277-T2-TXA"]["list"] == "alternate"
    assert rows["2277-T2-TXB"]["in_alternate_week"] is True
    assert rows["2277-T2-TXA"]["in_alternate_week"] is False


def test_a_course_moved_to_the_alternate_list_is_shown_as_one(client):
    item = add(client, offering_id="2416-T1")["items"][0]
    assert (item["in_week"], item["in_alternate_week"]) == (True, False)
    moved = client.post("/api/move", json={"item_id": item["id"], "list": "alternate"}).get_json()["state"]["items"][0]
    assert (moved["in_week"], moved["in_alternate_week"]) == (False, True)


# ---------- the clash notes of the list stay as they are (LN R13) ----------

def test_the_list_warns_before_an_alternate_is_added(client):
    # Fundamentals TXA would meet Impact Investments TXA, which is in the week: its section says so before the plus
    state = add(client, section_id="2277-T2-TXA")
    assert state["section_warnings"]["2652-S1-TXA"] == ["Impact Investments TXA (T2)"]


def test_an_alternate_warns_nobody(client):
    # only the week counts for clashes and for "fits my week": with Fundamentals as an alternate, Impact Investments TXA still fits
    state = add(client, offering_id="2652-S1", list="alternate")
    assert "2277-T2-TXA" not in state["section_warnings"]


# ---------- spring has no timetable yet, so no week ----------

def test_a_spring_alternate_has_nothing_to_draw(client):
    client.post("/api/settings", json={"programme": "Management", "semester": "Spring"})
    item = add(client, offering_id="2964-T3", list="alternate")["items"][0]
    assert item["list"] == "alternate"
    assert item["section_id"] is None
    assert item["meetings"] == []


# ---------- the page ----------

def test_the_page_has_the_band_that_says_where_a_plus_goes(client):
    # hidden until "Add alternate course" starts filling the list; planner.js shows it and "Done" ends it
    for path in ("/", "/bids"):
        html = client.get(path).get_data(as_text=True)
        band = html.split('id="alternate-banner"')[1].split("</div>")[0]
        assert " hidden" in band.split(">")[0], path
        assert "Adding to your alternate list." in band and "+ puts a course there." in band, path
        assert 'id="alternate-done"' in band and ">Done<" in band, path
