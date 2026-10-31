"""The guards around the LLM (app/ai_guard.py). Pure functions: no network, no database."""
import pytest

from app import ai_guard as g


# --- input: personal data -------------------------------------------------------------------------------------

def test_email_keeps_its_domain_and_loses_the_rest():
    assert g.mask_email("billing@acme.example.com") == "b***@acme.example.com"
    assert g.mask_text("Write to bob.smith@acme.example.com today") == "Write to b***@acme.example.com today"


def test_phone_numbers_are_replaced_but_dates_and_amounts_are_not():
    assert g.mask_text("Call +1 (888) 555-0142 now") == f"Call {g.MASKED_PHONE} now"
    assert g.mask_text("Call 0048 12 345 67 89") == f"Call {g.MASKED_PHONE}"
    for keep in ("Service period 2026-10-01 to 2026-10-31", "Due 31.10.2026", "Total 1,200.50 USD", "Qty 12 at 9.99"):
        assert g.mask_text(keep) == keep


def test_links_lose_their_query_string_and_fragment():
    assert g.mask_text("Pay at https://pay.example/inv/7?token=SECRET&u=1#top today") == "Pay at https://pay.example/inv/7 today"
    assert g.strip_url_query("https://a.example/x?y=1") == "https://a.example/x"


def test_empty_input():
    assert g.mask_text(None) == "" and g.mask_text("") == ""


# --- output: values must come from the input ----------------------------------------------------------------

SOURCE = (
    '{"supplier_email": "b***@acme.example.com", "amount": 349.99, "currency": "USD", '
    '"note": "Pay at https://pay.example/inv/7 or call [phone]"}'
)


def test_values_present_in_the_input_are_grounded():
    text = "The sender b***@acme.example.com asks $349.99 (349.99 USD) via https://pay.example/inv/7."
    assert g.ungrounded_values(text, SOURCE) == []


def test_an_invented_email_link_phone_or_amount_is_found():
    assert g.ungrounded_values("Contact billing@acme.example.com", SOURCE) == ["billing@acme.example.com"]
    assert g.ungrounded_values("Real mail is b***@evil.example", SOURCE) == ["b***@evil.example"]
    assert g.ungrounded_values("Go to https://paypa1.example/login", SOURCE) == ["https://paypa1.example/login"]
    assert g.ungrounded_values("Call +1 888 555 0142", SOURCE) == ["+1 888 555 0142"]
    assert g.ungrounded_values("It asks for $1,499.00", SOURCE) == ["$1,499.00"]
    assert g.ungrounded_values("It asks for 120 EUR", SOURCE) == ["120 EUR"]


def test_amounts_are_compared_as_numbers_not_as_text():
    assert g.ungrounded_values("The total is 349.990 USD", SOURCE) == []
    assert g.ungrounded_values("The total is $349.99", '{"amount": 349.990}') == []


def test_words_and_small_numbers_are_not_values():
    assert g.ungrounded_values("The invoice is 2 days overdue and has 3 signs.", SOURCE) == []
    assert g.ungrounded_values("", SOURCE) == []


def test_redact_replaces_only_the_invented_value():
    out = g.redact_ungrounded("Pay $349.99 to evil@bad.example.", SOURCE)
    assert out == f"Pay $349.99 to {g.REDACTED}."


# --- output: no certainty ------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "This invoice is a scam.", "It is definitely fraudulent.", "It's a scam", "Clearly a phishing attempt",
    "This is confirmed fraud.", "The invoice is safe to pay.", "The supplier is legitimate.",
    "Это мошенничество.", "Это точно мошенники", "Счёт безопасен", "Можно смело платить",
])
def test_statements_of_certainty_are_caught(text):
    assert g.overclaims(text)


@pytest.mark.parametrize("text", [
    "The invoice shows signs of fraud and needs checking.", "There are signs that it may be a scam.",
    "Nothing here proves the sender is legitimate, so verify it.", "Обнаружены признаки мошенничества, нужна проверка.",
    "The email domain does not match the brand.", "",
])
def test_cautious_wording_passes(text):
    assert not g.overclaims(text)
