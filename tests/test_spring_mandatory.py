"""A11: the mandatory courses of the spring are in the catalogue, although Nova has not published the spring timetable.

Which courses: seed/spring_mandatory.csv, read from Nova's programme pages and NOVA's programme catalogue (docs/data.md).
"""
import pytest

import logic


@pytest.fixture
def visitor():
    import app as lance
    lance.app.config.update(TESTING=True)
    return lance.app.test_client()


def spring_of(client, programme):
    client.post("/api/settings", json={"programme": programme, "semester": "Spring"})
    return {course["id"]: course for course in client.get("/api/catalogue").get_json()}


def mandatory_in(catalogue):
    return sorted(course["id"] for course in catalogue.values() if course["kind"] == "mandatory")


def test_business_analytics_has_its_three_mandatory_courses_of_term_three(visitor):
    catalogue = spring_of(visitor, "Business Analytics")
    assert mandatory_in(catalogue) == ["2606-T3", "2761-T3", "2767-T3"]
    assert catalogue["2767-T3"]["name"] == "Machine Learning"
    assert catalogue["2767-T3"]["ects"] == 3.5


def test_public_policy_has_its_three_mandatory_courses_of_term_three(visitor):
    catalogue = spring_of(visitor, "Public Policy")
    assert mandatory_in(catalogue) == ["2739-T3", "2744-T3", "2747-T3"]
    assert catalogue["2747-T3"]["name"] == "Public Policy II"


def test_economics_chooses_between_micro_and_macroeconometrics(visitor):
    # Nova's programme page: "Macroeconometrics OR Microeconometrics". Both are listed, the student picks the one they take.
    assert mandatory_in(spring_of(visitor, "Economics")) == ["2165-S2", "2168-S2"]


def test_impact_entrepreneurship_has_its_project_and_data_science_for_impact(visitor):
    catalogue = spring_of(visitor, "Impact Entrepreneurship")
    assert mandatory_in(catalogue) == ["2710-T4", "2756-S2", "2763-T3", "2765-S2"]
    assert catalogue["2756-S2"]["ects"] == 7.0 and catalogue["2710-T4"]["ects"] == 3.5


def test_management_and_finance_offer_their_mandatory_courses_again_in_spring(visitor):
    assert mandatory_in(spring_of(visitor, "Management")) == [
        "2336-T3", "2414-S2", "2431-S2", "2459-S2", "2463-T3", "2581-S2", "2584-S2", "2786-T3", "2786-T4"]
    assert mandatory_in(spring_of(visitor, "Finance")) == ["2229-S2"]


def test_a_course_keeps_its_name_and_ects_from_the_fall(visitor):
    spring = spring_of(visitor, "Management")
    assert spring["2431-S2"]["name"] == "Marketing Management" and spring["2431-S2"]["ects"] == 7.0
    assert spring["2786-T3"]["name"] == "Research Methods in Management" and spring["2786-T3"]["ects"] == 3.5


def test_without_a_timetable_a_mandatory_course_is_added_without_a_section(visitor):
    spring_of(visitor, "Management")
    answer = visitor.post("/api/add", json={"offering_id": "2431-S2"}).get_json()
    assert answer["error"] is None
    item = answer["state"]["items"][0]
    assert item["list"] == "mandatory" and item["section_id"] is None
    # LN R16: it counts for the estimated points like any mandatory course
    assert answer["state"]["plan"]["points"] == logic.estimated_points(7)


def test_the_sheet_of_a_new_spring_course_opens(visitor):
    spring_of(visitor, "Business Analytics")
    sheet = visitor.get("/api/sheet/2767-T3").data.decode()
    assert "Machine Learning" in sheet and "3.5 ECTS" in sheet


def test_the_fall_is_untouched():
    fall = [offering for offering in logic.all_offerings().values() if offering["semester"] == "Fall"]
    assert len(fall) == 137
    assert len(logic.all_sections()) == 245
