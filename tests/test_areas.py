"""LN R20: areas of expertise. A student may choose one area of their programme; its courses get a group of their own
in the course list, and the group says how far the plan is: at least 21 ECTS of electives in the area, including every
core course of the area (if it has any) or at least one "core optional" course.

Which courses belong to which area: seed/areas.csv, read from the programmes' pages on SharePoint (docs/data.md).
"""
import csv
import os
import sqlite3

import pytest

import db
import logic

HERE = os.path.dirname(os.path.abspath(__file__))
AREAS_FILE = os.path.join(HERE, "..", "seed", "areas.csv")


@pytest.fixture
def visitor():
    import app as lance
    lance.app.config.update(TESTING=True)
    return lance.app.test_client()


def plan_in(programme, area, semester="Fall"):
    plan = db.load_plan(db.create_plan(programme, semester, 200))
    assert logic.update_settings(plan, programme, semester, 200, False, area=area) is None
    return db.load_plan(plan["id"])


def add(plan, *offering_ids):
    for offering_id in offering_ids:
        assert logic.add_to_plan(plan, offering_id=offering_id) is None


def in_semester(plan, semester):
    assert logic.update_settings(plan, plan["programme"], semester, 200, False) is None
    return db.load_plan(plan["id"])


# ---------- the content ----------

def test_every_area_course_with_a_code_is_a_course_lance_knows():
    with open(AREAS_FILE, newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert rows
    for row in rows:
        assert row["role"] in ("core", "core_optional", "elective", "elsewhere"), row
        if row["role"] == "elsewhere":
            # taught outside Nova SBE: no code, but a name and its ECTS
            assert row["code"] == "" and row["name"] and float(row["ects"]) > 0, row
        else:
            assert f"{row['code']}-{row['term']}" in logic.all_offerings(), row


def test_each_programme_offers_the_areas_of_its_sharepoint_page():
    assert logic.areas_of("Finance") == ["Corporate Finance", "Financial Markets"]
    assert logic.areas_of("Economics") == ["Business and Data Analytics", "International Development",
                                           "Macroeconomics and Financial Markets", "Public Policy", "Sustainability"]
    assert logic.areas_of("Management") == ["Digital and Data-Driven Business", "Entrepreneurship", "Financial Management",
                                            "Marketing", "Operations Management", "Strategy and International Business",
                                            "Sustainability"]
    assert logic.areas_of("Impact Entrepreneurship") == ["Health Innovation"]
    assert logic.areas_of("Business Analytics") == []
    assert logic.areas_of("Public Policy") == []
    assert logic.areas_of("") == []


def test_no_area_course_is_mandatory_in_its_own_programme():
    # the area group takes courses out of the electives, never out of the mandatory courses
    for programme in db.load_programmes():
        kinds = db.load_programme_kinds(programme)
        for row in db.load_areas(programme):
            if row["code"]:
                assert kinds.get(f"{row['code']}-{row['term']}") != "mandatory", (programme, row)


# ---------- choosing an area ----------

def test_a_chosen_area_is_saved_with_the_plan(visitor):
    visitor.post("/api/settings", json={"programme": "Management"})
    answer = visitor.post("/api/settings", json={"area": "Marketing"}).get_json()
    assert answer["error"] is None
    assert answer["state"]["plan"]["area"] == "Marketing"
    assert "Marketing" in answer["state"]["areas"]


def test_an_area_of_another_programme_is_refused_and_changes_nothing():
    plan = plan_in("Management", "Marketing")
    assert logic.update_settings(plan, "Management", "Fall", 200, False, area="Corporate Finance") == "Unknown area of expertise."
    assert db.load_plan(plan["id"])["area"] == "Marketing"


def test_changing_the_programme_clears_the_area():
    plan = plan_in("Management", "Sustainability")
    # Economics has a Sustainability area too, with other courses: the student chooses again
    assert logic.update_settings(plan, "Economics", "Fall", 200, False) is None
    assert db.load_plan(plan["id"])["area"] == ""


def test_other_settings_keep_the_area():
    plan = plan_in("Finance", "Financial Markets")
    assert logic.update_settings(plan, "Finance", "Spring", 300, True) is None
    assert db.load_plan(plan["id"])["area"] == "Financial Markets"


def test_no_area_is_a_choice_too():
    plan = plan_in("Finance", "Corporate Finance")
    assert logic.update_settings(plan, "Finance", "Fall", 200, False, area="") is None
    assert db.load_plan(plan["id"])["area"] == ""
    assert logic.state_of(logic.load_plan(plan["id"]))["area"] is None


def test_a_database_from_before_areas_gets_the_new_column(tmp_path, monkeypatch):
    old = str(tmp_path / "old.db")
    with sqlite3.connect(old) as connection:
        connection.execute("""CREATE TABLE plans (id TEXT PRIMARY KEY, programme TEXT NOT NULL, semester TEXT NOT NULL,
                              points INTEGER NOT NULL, has_bonus INTEGER NOT NULL, created_at TEXT NOT NULL)""")
        connection.execute("INSERT INTO plans VALUES ('old', 'Finance', 'Fall', 120, 0, '2026-11-01')")
    monkeypatch.setattr(db, "DB_PATH", old)
    db.init_db()
    assert db.load_plan("old")["area"] == ""


# ---------- the course list ----------

def test_the_course_list_marks_the_courses_of_the_chosen_area():
    catalogue = {course["id"]: course for course in logic.catalogue(plan_in("Management", "Marketing"))}
    assert catalogue["2327-S1"]["area_role"] == "core_optional"   # Brand Management
    assert catalogue["2613-T1"]["area_role"] == "elective"        # Asian Brands
    assert catalogue["2477-S1"]["area_role"] is None              # Introduction to Programming: another area


def test_without_an_area_no_course_is_marked():
    plan = db.load_plan(db.create_plan("Management", "Fall", 200))
    assert all(course["area_role"] is None for course in logic.catalogue(plan))


def test_an_area_course_of_another_programme_is_still_in_the_area():
    # Financial Intermediation is no elective of Finance in fall, but its area lists it
    catalogue = {course["id"]: course for course in logic.catalogue(plan_in("Finance", "Financial Markets"))}
    assert catalogue["2240-T1"]["area_role"] == "elective"


# ---------- how far the plan is ----------

def test_an_area_with_a_core_course_needs_it():
    plan = plan_in("Management", "Sustainability")
    progress = logic.area_progress(plan)
    assert progress["name"] == "Sustainability"
    assert progress["ects"] == 0 and progress["needed"] == 21
    assert progress["core_missing"] == ["Fundamentals on Environment and Sustainability"]
    assert progress["done"] is False
    add(plan, "2652-S1")
    progress = logic.area_progress(plan)
    assert progress["ects"] == 7 and progress["core_missing"] == []


def test_an_area_with_core_options_needs_one_of_them():
    plan = plan_in("Management", "Marketing")
    progress = logic.area_progress(plan)
    assert progress["core_options"] == ["Brand Management", "Consumer Behavior", "Integrated Marketing Communications"]
    add(plan, "2337-T1")   # Integrated Marketing Communications
    progress = logic.area_progress(plan)
    assert progress["core_options"] == [] and progress["core_missing"] == []
    assert progress["ects"] == 3.5


def test_an_area_without_core_courses_is_done_at_21_ects():
    plan = plan_in("Management", "Strategy and International Business")
    add(plan, "2582-S1", "2484-S1")
    assert logic.area_progress(plan)["done"] is False
    add(plan, "2698-S1")
    progress = logic.area_progress(plan)
    assert progress["ects"] == 21 and progress["done"] is True


def test_a_core_course_counts_in_any_of_its_terms_and_both_semesters_count():
    plan = plan_in("Finance", "Financial Markets")
    assert logic.area_progress(plan)["core_missing"] == ["Asset Management", "Derivatives"]
    add(plan, "2218-T2")   # Derivatives in fall
    assert logic.area_progress(plan)["core_missing"] == ["Asset Management"]
    plan = in_semester(plan, "Spring")
    add(plan, "2214-T3")   # Asset Management in spring
    progress = logic.area_progress(plan)
    assert progress["core_missing"] == []
    assert progress["ects"] == 7   # 3.5 in fall and 3.5 in spring


def test_only_the_primary_list_counts_and_a_course_counts_once():
    plan = plan_in("Management", "Strategy and International Business")
    add(plan, "2582-S1")
    sections = [section["id"] for section in db.load_sections("2582-S1")]
    if len(sections) > 1:
        assert logic.add_to_plan(plan, section_id=sections[1]) is None   # a backup section of the same course
    assert logic.area_progress(plan)["ects"] == 7
    item = db.load_items(plan["id"])[0]
    assert logic.move_item(plan, item["id"], list_name="alternate") is None
    assert logic.area_progress(plan)["ects"] == 0


def test_courses_taught_elsewhere_are_named_but_not_counted():
    plan = plan_in("Impact Entrepreneurship", "Health Innovation", semester="Spring")
    progress = logic.area_progress(plan)
    assert progress["core_missing"] == ["Value-Based Health Care"]
    assert [course["name"] for course in progress["elsewhere"]] == ["Aging and Health", "Nutrition through Lifecycle"]
    add(plan, "2580-S2", "2135-T3", "2158-T4")
    progress = logic.area_progress(plan)
    assert progress["ects"] == 14 and progress["core_missing"] == [] and progress["done"] is False


def test_the_state_carries_the_areas_and_the_progress(visitor):
    visitor.post("/api/settings", json={"programme": "Finance", "area": "Corporate Finance"})
    state = visitor.get("/api/state").get_json()["state"]
    assert state["areas"] == ["Corporate Finance", "Financial Markets"]
    assert state["area"]["name"] == "Corporate Finance"
    assert state["area"]["core_missing"] == ["Applied Corporate Finance"]


# ---------- saying the rule ----------

def test_the_progress_says_which_kind_of_core_rule_the_area_has():
    # the page turns this into its one line: "including every core course", "including one core option", or nothing more
    assert logic.area_progress(plan_in("Finance", "Financial Markets"))["core_rule"] == "core"
    assert logic.area_progress(plan_in("Management", "Marketing"))["core_rule"] == "core_optional"
    assert logic.area_progress(plan_in("Management", "Strategy and International Business"))["core_rule"] == "none"


def test_the_rules_page_explains_areas_and_opens_on_that_question(visitor):
    page = visitor.get("/rules").get_data(as_text=True)
    assert 'id="areas"' in page and "21 ECTS" in page and "core optional" in page
    assert '<details class="rule" id="areas">' in page   # closed when nobody asked for it
    opened = visitor.get("/rules?about=areas").get_data(as_text=True)
    assert '<details class="rule" id="areas" open>' in opened
