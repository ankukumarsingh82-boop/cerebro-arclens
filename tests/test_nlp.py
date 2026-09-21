from app.nlp import analyze_text
from app.sarcasm import score_sarcasm


def test_oh_great_is_sarcastic():
    result = score_sarcasm("Oh great. Just what we needed an hour before the investor demo.")
    assert result["flag"] is True
    assert result["score"] >= 0.55
    assert result["cues"]


def test_love_the_welcome_is_sarcastic():
    result = score_sarcasm("Wow. Love the welcome.", previous_text="Did you forget again?")
    assert result["flag"] is True


def test_thanks_a_lot_alone_is_flagged_or_ironic():
    result = score_sarcasm("Great. So I am eating alone. Again. Thanks a lot.")
    assert result["irony"] is True
    assert result["score"] >= 0.45


def test_plain_thanks_is_not_sarcastic():
    result = score_sarcasm("Thanks for landing the sample parser.")
    assert result["flag"] is False
    assert result["score"] < 0.55


def test_positive_message_has_positive_polarity():
    tone = analyze_text("Nice. Ship it after I glance at the dashboard.")
    assert tone["polarity"] > 0.2
    assert tone["label"] in {"supportive", "warm", "excited", "neutral", "forward-looking"}


def test_disaster_is_negative():
    tone = analyze_text("Rolling back. This is a disaster.")
    assert tone["polarity"] < -0.2
    assert tone["label"] in {"angry", "furious", "frustrated", "tense", "anxious", "sad"}
