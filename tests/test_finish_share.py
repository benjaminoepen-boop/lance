"""The last step asks for rank lists, and says who it asks: only a student who has bid in a round before has any.
A first-semester student is told so, instead of being sent to a page they cannot use yet."""
import re

import logic


def finish_page(client):
    return client.get("/nova").get_data(as_text=True)


def test_the_finish_page_asks_students_who_bid_before_for_their_rank_lists(client):
    page = finish_page(client)
    assert "Have you bid in a round before?" in page
    assert "tab <i>Rank</i>" in page          # where the lists are on Nova's platform
    assert 'href="/share"' in page             # the share page, with its video, stays where it was


def test_it_says_what_the_lists_are_good_for(client):
    assert "how many bidding points a place in a course has needed in past rounds" in finish_page(client)


def test_it_tells_a_first_semester_student_that_there_is_nothing_to_share_yet_before_the_button(client):
    page = finish_page(client)
    assert "First semester at Nova SBE?" in page
    assert page.index("First semester at Nova SBE?") < page.index("Share my rank lists")


def test_it_says_that_the_link_leads_to_a_video(client):
    page = finish_page(client)
    assert "short video that shows how to share your rank lists" in page
    assert page.index("short video") < page.index("Share my rank lists")


def test_it_shows_how_many_sections_have_a_bidding_history_already(client):
    numbers = logic.coverage()
    text = re.sub(r"\s+", " ", finish_page(client))
    assert f"{numbers['covered']} of {numbers['total']} sections" in text


def test_the_checklist_is_gone(client):
    page = finish_page(client)
    assert "Before you start on the platform" not in page
    assert "data-check" not in page


def test_the_footnote_is_only_the_disclaimer_now(client):
    page = finish_page(client)
    assert "the fall lists are out" not in page
    assert "Student project, not an official Nova SBE system." in page
