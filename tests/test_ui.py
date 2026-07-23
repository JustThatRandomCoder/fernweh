"""Tests for the typewriter text reveal and intro dialog paging (pure logic)."""

from fernweh.ui import IntroDialog, TypewriterText


def test_starts_with_nothing_revealed() -> None:
    typewriter = TypewriterText("hello world")
    assert typewriter.visible_text() == ""
    assert typewriter.done is False


def test_empty_text_is_immediately_done() -> None:
    typewriter = TypewriterText("")
    assert typewriter.done is True


def test_reveals_characters_over_time() -> None:
    typewriter = TypewriterText("hello world")
    typewriter.update(dt=0.1, hardship_level=0)
    assert 0 < len(typewriter.visible_text()) < len("hello world")


def test_completes_and_stops_advancing() -> None:
    typewriter = TypewriterText("hi")
    typewriter.update(dt=10.0, hardship_level=0)
    assert typewriter.done is True
    assert typewriter.visible_text() == "hi"
    typewriter.update(dt=10.0, hardship_level=0)
    assert typewriter.visible_text() == "hi"


def test_higher_hardship_reveals_more_slowly() -> None:
    calm = TypewriterText("a" * 100)
    calm.update(dt=0.5, hardship_level=0)

    hardship = TypewriterText("a" * 100)
    hardship.update(dt=0.5, hardship_level=2)

    assert len(hardship.visible_text()) < len(calm.visible_text())


def test_skip_reveals_everything_immediately() -> None:
    typewriter = TypewriterText("hello world")
    typewriter.skip()
    assert typewriter.done is True
    assert typewriter.visible_text() == "hello world"


def test_reset_restarts_reveal_for_new_text() -> None:
    typewriter = TypewriterText("first")
    typewriter.skip()
    typewriter.reset("second")
    assert typewriter.done is False
    assert typewriter.visible_text() == ""


def test_intro_dialog_advances_through_all_pages() -> None:
    dialog = IntroDialog(pages=("one", "two", "three"))
    assert dialog.done is False
    dialog.advance()
    assert dialog.page_index == 1
    dialog.advance()
    assert dialog.done is False
    dialog.advance()
    assert dialog.done is True


def test_intro_dialog_can_be_reopened_fresh() -> None:
    dialog = IntroDialog(pages=("one", "two"))
    dialog.advance()
    dialog.advance()
    assert dialog.done is True
    fresh = IntroDialog(pages=dialog.pages)
    assert fresh.page_index == 0
    assert fresh.done is False
