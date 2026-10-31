from pathlib import Path

import pytest

from app.email_invoice import parse_invoice_email
from app.email_rules import assess_email
from app.normalize import normalize_email

DIR = Path(__file__).parent / "fixtures/emails"
mail_html = lambda name: (DIR / f"{name}.html").read_text()


def judge(html, earlier=None):
    """Findings for `html`, compared with the earlier email `earlier` (HTML) of the same invoice."""
    mail = parse_invoice_email(html)
    previous = normalize_email(earlier).model_dump(mode="json") if earlier else None
    result = assess_email(mail, normalize_email(html, mail).model_dump(mode="json"), previous)
    return {f["label"]: f for f in result["findings"]}, result


def updated(**swap):
    html = mail_html("0068_updated")
    for old, new in swap.items():
        html = html.replace(old.replace("__", " "), new)
    return html


def test_an_ordinary_first_email_has_nothing_to_flag():
    found, result = judge(mail_html("0068_new"))
    assert found == {} and result["comparison"] == []


def test_amount_raised_after_sending_is_flagged_with_both_figures():
    found, result = judge(mail_html("0068_updated"), mail_html("0068_new"))
    f = found["Amount raised after sending"]
    assert f["severity"] == "medium" and "100.00" in f["text"] and "175.00" in f["text"] and "+75%" in f["text"]
    assert result["comparison"][0] == {"field": "Amount (earlier email)", "current": "175.00 USD", "previous": "100.00 USD", "differs": True}


def test_amount_more_than_doubled_is_high():
    html = updated(**{"$175.00": "$320.00"})
    assert judge(html, mail_html("0068_new"))[0]["Amount raised sharply after sending"]["severity"] == "high"


def test_a_lower_amount_is_not_a_finding():
    found, _ = judge(updated(**{"$175.00": "$90.00"}), mail_html("0068_new"))
    assert "Amount raised after sending" not in found and "Amount raised sharply after sending" not in found


def test_due_date_moved_earlier_is_flagged():
    found, _ = judge(updated(**{"$175.00": "$100.00", "Nov__14,__2026": "Nov 2, 2026"}), mail_html("0068_new"))
    assert found["Due date moved earlier"]["severity"] == "medium"
    assert "Updated, but nothing visible changed" not in found


def test_a_later_due_date_is_a_change_but_not_a_warning():
    found, _ = judge(updated(**{"$175.00": "$100.00", "Nov__14,__2026": "Nov 30, 2026"}), mail_html("0068_new"))
    assert "Due date moved earlier" not in found and "Updated, but nothing visible changed" not in found


def test_renamed_items_are_flagged():
    found, _ = judge(updated(**{"$175.00": "$100.00", "Test__item": "Premium support package"}), mail_html("0068_new"))
    assert "Premium support package" in found["Items changed after sending"]["text"]


def test_currency_change_is_high():
    html = updated(**{"$175.00": "$100.00"}).replace("USD", "EUR")
    assert judge(html, mail_html("0068_new"))[0]["Currency changed after sending"]["severity"] == "high"


def test_an_update_where_nothing_visible_changed_points_to_the_note():
    """PayPal's update email leaves the note out, so a note-only edit looks like an identical email."""
    found, _ = judge(updated(**{"$175.00": "$100.00"}), mail_html("0068_new"))
    f = found["Updated, but nothing visible changed"]
    assert f["severity"] == "medium" and "note" in f["text"]


def test_an_update_without_an_earlier_email_says_it_cannot_compare():
    found, _ = judge(mail_html("0068_updated"))
    assert found["Changes not checked: no earlier email"]["severity"] == "ok" and len(found) == 1


def test_the_missing_note_of_an_update_email_is_never_reported_as_a_change():
    found, _ = judge(mail_html("0068_updated"), mail_html("0068_new"))  # the first email has a note, the update has none
    assert not any("note" in f["label"].lower() for f in found.values())


def test_a_button_that_leaves_paypal_is_high():
    html = mail_html("0068_new").replace("https://www.sandbox.paypal.com/invoice/payerView/details/", "https://paypal-invoices.example/pay/", 1)
    found, _ = judge(html)
    f = found["Payment link does not lead to PayPal"]
    assert f["severity"] == "high" and "paypal-invoices.example" in f["text"]


def test_a_link_that_reads_as_one_address_and_opens_another_is_high():
    html = mail_html("0068_new").replace("</table>\n", '<a href="https://evil.example/x">www.paypal.com/help</a></table>\n', 1)
    assert judge(html)[0]["A link shows one address but opens another"]["severity"] == "high"


def test_another_pay_link_outside_paypal_is_medium_but_a_social_link_is_not_judged():
    base = mail_html("0068_new")
    pay = base.replace("</table>\n", '<a href="https://pay-now.example/x">Pay now</a></table>\n', 1)
    social = base.replace("</table>\n", '<a href="https://x.com/paypal">Follow us</a></table>\n', 1)
    assert judge(pay)[0]["Another link leads outside PayPal"]["severity"] == "medium"
    assert judge(social)[0] == {}


@pytest.mark.parametrize("html", ["", "hello", "<p>no links at all</p>"])
def test_garbage_gives_no_findings_and_no_crash(html):
    assert judge(html)[0] == {}
