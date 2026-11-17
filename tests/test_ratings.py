"""A7 and LN07: a course shows what students say on Uni Feedback. Lance collects no ratings of its own."""
import logic


def test_a_course_shows_its_rating_the_number_of_reviews_and_the_workload():
    rating = logic.course_rating("2477")     # Introduction to Programming, read on 17 Nov 2026
    assert rating["rating"] == 4.6
    assert rating["reviews"] == 18
    assert rating["workload"] == "Light"
    assert rating["url"] == "https://uni-feedback.com/en/courses/1649"


def test_a_course_nobody_reviewed_has_no_rating():
    assert logic.course_rating("2277") is None     # Impact Investments
    assert logic.course_rating("nope") is None


def test_every_rating_is_between_one_and_five_and_rests_on_at_least_one_review():
    ratings = logic.all_ratings()
    assert len(ratings) > 100
    for rating in ratings.values():
        assert 1 <= rating["rating"] <= 5
        assert rating["reviews"] >= 1
        assert rating["workload"] in ("Very light", "Light", "Moderate", "Heavy", "Very heavy")


def test_the_list_carries_the_rating_of_each_course(client):
    catalogue = {course["id"]: course for course in client.get("/api/catalogue").get_json()}
    assert catalogue["2477-S1"]["rating"] == 4.6
    assert catalogue["2477-S1"]["reviews"] == 18
    assert catalogue["2277-T2"]["rating"] is None


def test_the_course_sheet_names_the_rating_and_where_it_comes_from(client):
    sheet = client.get("/api/sheet/2477-S1").data.decode()
    assert "4.6" in sheet and "18 reviews" in sheet and "Light" in sheet
    assert 'href="https://uni-feedback.com/en/courses/1649"' in sheet


def test_the_course_sheet_says_so_when_nobody_reviewed_the_course(client):
    sheet = client.get("/api/sheet/2277-T2").data.decode()
    assert "No reviews on Uni Feedback yet" in sheet


def test_lance_takes_no_ratings_itself(client):
    # rating while bidding confused people (advisor's feedback, 17 Nov 2026): the form and its address are gone
    assert client.post("/course/2477-S1/rate", data={"overall": "4"}).status_code in (404, 405)
    assert "Rate this course" not in client.get("/api/sheet/2477-S1").data.decode()
