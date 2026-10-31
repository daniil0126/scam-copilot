"""Собирает backend/tests/dataset/cases.json (контракт Invoice v0.6).

Тексты примечаний взяты из eval_notes.json, eval_test.json, eval_heldout.json и suspicious.json
(поле origin у каждого случая). Остальные поля Invoice заполнены по контракту, недостающее = null.

    python backend/tests/dataset/build_dataset.py
"""
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).with_name("cases.json")
ACCOUNT = "acc_dataset"
NH = {"name": "Nordhost GmbH", "email": "billing@nordhost.test", "phone": "+49 30 1234567"}
IBAN = "DE91100000000123456789"
H_NOTE = f"Hosting. Pay to IBAN {IBAN}. Questions? billing@nordhost.test"
HIST_ID = "nordhost"


def inv(id_, number="0042", amount="35.00", currency="EUR", note=None, sender=NH, status="SENT",
        source="paypal_api", account=ACCOUNT, day="2026-10-28", due=None, terms=None,
        item="Hosting plan Pro", links=(), recipient="buyer@example.org", items=None):
    s = sender or {}
    if due is None and day:
        due = (date.fromisoformat(day) + timedelta(days=14)).isoformat()
    if items is None and item and amount:
        items = [{"name": item, "description": None, "quantity": "1", "unitAmount": amount}]
    links = ([f"https://www.paypal.com/invoice/p/#{id_}"] if source == "paypal_api" else []) + list(links)
    api = source == "paypal_api"
    d = {
        "id": id_, "accountId": account, "source": source, "invoiceNumber": number, "status": status,
        "amount": amount, "currency": currency, "invoiceDate": day, "dueDate": due,
        "senderName": s.get("name"), "senderLegalName": None, "senderEmail": s.get("email"),
        "senderPhone": s.get("phone"), "recipientName": None, "recipientEmail": recipient,
        "paymentTerms": terms, "items": items, "paymentLinks": links or None, "note": note,
        "createdAt": f"{day}T09:00:00Z" if api and day else None,
        "updatedAt": f"{day}T09:00:00Z" if api and day else None,
    }
    d["contentHash"] = "sha256:" + hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()
    return d


def history():
    days = ["2026-04-28", "2026-05-28", "2026-06-28", "2026-07-28", "2026-08-28", "2026-09-28"]
    amounts = ["35.00", "35.00", "29.00", "35.00", "35.67", "35.00"]
    return [inv(f"INV2-HIST-NH-{i + 1:02d}", number=f"{36 + i:04d}", amount=a, note=H_NOTE,
                status="PAID", day=d) for i, (d, a) in enumerate(zip(days, amounts))]


CASES = []


def add(cid, category, description, invoice, flagged, hist=HIST_ID, signals=(), insufficient=None, origin=None):
    if insufficient is None:
        insufficient = hist is None or invoice["accountId"] is None
    CASES.append({
        "caseId": cid, "category": category, "description": description, "origin": origin,
        "history": hist, "invoice": invoice,
        "expected": {"flagged": flagged, "signals": list(signals), "insufficientData": insufficient},
    })


# --- нормальные: 28 -------------------------------------------------------------------------
NORMAL = [
    ("L01", "eval_notes.json:L01", "Hosting plan Pro, period 01.11.2026 - 30.11.2026. Thank you for your business!", {}),
    ("L02", "eval_notes.json:L02", "Payment to DE91100000000123456789. Invoice INV-2026-001234, PO 4500123456.", {}),
    ("L03", "eval_notes.json:L03", "Please pay DE91 1000 0000 0123 4567 89 within 30 days (Net 30).", {"terms": "Net 30", "due": "2026-11-27"}),
    ("L04", "eval_notes.json:L04", "Hosting for November. Questions? Contact billing@nordhost.test", {}),
    ("L05", "eval_notes.json:L05", "Due date 2026-11-15, amount 29.00 EUR. Auto-renewal on 2026-12-01.", {"amount": "29.00", "due": "2026-11-15"}),
    ("L07", "eval_notes.json:L07", "Thank you!", {}),
    ("L08", "eval_notes.json:L08", "Domain renewal example.com for 1 year, 12.99 EUR.", {"amount": "12.99", "item": "Domain renewal example.com", "_nohist": True}),
    ("L09", "eval_notes.json:L09", "Reminder: this invoice is due on 15.11.2026.", {"due": "2026-11-15"}),
    ("L10", "eval_notes.json:L10", "Pay by bank transfer. IBAN: DE91100000000123456789. Reference: INV-2026-001234", {}),
    ("L11", "eval_notes.json:L11", "Dear customer, your VPS plan was renewed. Customer ID 1234567890.", {}),
    ("L12", "eval_notes.json:L12", "Prices include 23% VAT. Total 35.67 EUR.", {"amount": "35.67"}),
    ("L13", "eval_notes.json:L13", "Questions about this invoice? Our support team: +49 30 1234567.", {}),
    ("L15", "eval_notes.json:L15", "Your site loads quickly thanks to the new CDN add-on (included in your plan).", {}),
    ("L16", "eval_notes.json:L16", "Payment received, thank you. This invoice is already paid.", {"status": "PAID"}),
    ("L17", "eval_notes.json:L17", "Billing period: Nov 2026. Payment terms: net 14 days.", {"terms": "Net 14"}),
    ("L18", "eval_notes.json:L18", "IBAN DE91100000000123456789 (once again: DE91100000000123456789).", {}),
    ("TL01", "eval_test.json:TL01", "Faktura za usługi hostingowe za listopad 2026. Dziękujemy!", {}),
    ("TL02", "eval_test.json:TL02", "You can download this invoice as PDF from your customer portal after you sign in.", {}),
    ("TL03", "eval_test.json:TL03", "To update your payment method, open Settings > Billing in your account.", {}),
    ("TL04", "eval_test.json:TL04", "If you have questions about this invoice, reply to this email and our billing team will help you.", {}),
    ("TL05", "eval_test.json:TL05", "Your overpayment from last month (12.00 EUR) was credited to your account balance.", {}),
    ("TL06", "eval_test.json:TL06", "This invoice was generated automatically. Prices are in EUR, 23% VAT included.", {}),
    ("TL07", "eval_test.json:TL07", "Your plan renews automatically on 2026-12-01. You can cancel at any time in the portal.", {}),
    ("TL08", "eval_test.json:TL08", "Late payment interest may apply after the due date, as described in our terms.", {}),
    ("TL09", "eval_test.json:TL09", "A SEPA payment QR code is included at the bottom of this invoice.", {}),
    ("TL10", "eval_test.json:TL10", "Please find the PDF invoice attached.", {}),
    ("HL01", "eval_heldout.json:HL01", "Our bank details are unchanged. Please continue paying to the IBAN on your previous invoices.", {}),
    ("HL07", "eval_heldout.json:HL07", "You can view this invoice at https://nordhost.test/invoices/2026-11 after logging in.",
     {"links": ["https://nordhost.test/invoices/2026-11"]}),
]
for n, (cid, origin, note, kw) in enumerate(NORMAL, 1):
    kw = dict(kw)
    nohist = kw.pop("_nohist", False)
    desc = "Обычный ежемесячный счёт известного поставщика Nordhost: сумма и реквизиты как в истории, текст безобидный."
    if nohist:
        desc = "Продление домена у известного поставщика, но другой продукт: истории по такой сумме нет, поэтому история не привязана."
    if cid == "L13":
        desc = "Телефон в тексте совпадает с телефоном поставщика в истории, это не PHONE_IN_TEXT."
    if cid == "HL07":
        desc = "Ссылка в тексте ведёт на собственный домен поставщика (nordhost.test), не должна давать SUSPICIOUS_LINK."
    if cid in ("L02", "L03", "L10", "L18", "HL01"):
        desc = "В тексте тот же IBAN, что в истории, или ссылка на прежние реквизиты: смены реквизитов нет."
    add(f"N{n:02d}", "normal", desc, inv(f"INV2-DS-N{n:02d}", note=note, **kw), False,
        hist=None if nohist else HIST_ID, origin=origin)

# --- подозрительные: 13 ---------------------------------------------------------------------
NHF = [  # поставщик Nordhost с историей, подозрительный текст
    ("TF01", "eval_test.json:TF01", "From now on our partner company Delta Trade Ltd handles all collections for us. Please make payments to them.", ["SCAM_WORDING"], "Просьба платить третьей компании (BEC)."),
    ("TF02", "eval_test.json:TF02", "Download your invoice here: http://nordhost-invoices.example/d/88213", ["SUSPICIOUS_LINK"], "Фишинговая ссылка на чужой домен."),
    ("TF03", "eval_test.json:TF03", "Your server has been compromised. Install the attached remote support tool so that our engineer can fix it.", ["SCAM_WORDING"], "Техподдержка и удалённый доступ."),
    ("HF02", "eval_heldout.json:HF02", "Final notice from the tax authority: unpaid VAT, a penalty will be added. Pay via https://tax-office-pay.example/case/88213", ["SUSPICIOUS_LINK", "SCAM_WORDING"], "Угроза штрафа и ссылка на оплату на чужом домене."),
    ("HF05", "eval_heldout.json:HF05", "We accidentally overpaid your last invoice by 1,240 EUR. Please send the difference back to us.", ["SCAM_WORDING"], "Схема с переплатой."),
    ("HF07", "eval_heldout.json:HF07", "Scan the QR code in the attachment to complete the payment.", ["SCAM_WORDING"], "Оплата по QR-коду из вложения."),
    ("HF08", "eval_heldout.json:HF08", "Your account is overdue. Legal proceedings will be started tomorrow unless the full amount is paid.", ["SCAM_WORDING"], "Угроза судом, давление срочностью."),
    ("F08", "eval_notes.json:F08", "Pay the overdue amount with Google Play gift cards and send us the codes.", ["SCAM_WORDING"], "Оплата подарочными картами."),
    ("F10", "eval_notes.json:F10", "Send the payment in USDT to wallet TXq8a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p.", ["SCAM_WORDING"], "Оплата криптовалютой на кошелёк."),
]
for cid, origin, note, sigs, why in NHF:
    links = [u for u in note.split() if u.startswith("http")]
    add(f"S-{cid}", "suspicious", f"{why} Поставщик известен, история есть.", inv(f"INV2-DS-{cid}", note=note, links=links),
        True, signals=sigs, origin=origin)

STRANGERS = [  # неизвестные поставщики, истории нет
    ("F01", "eval_notes.json:F01", "billing@securprotect.test", "SecureProtect", "Your subscription to SecureProtect Pro was renewed for 499.00 USD. Call +1 (800) 555-0199 to cancel.", "499.00", "USD", ["PHONE_IN_TEXT", "SCAM_WORDING", "NEW_SENDER"], "Фальшивое продление и телефон «для отмены» (tech support scam)."),
    ("F03", "eval_notes.json:F03", "orders@store-receipts.test", "Store Receipts", "Thank you for your purchase of an iPhone 15. If you did not authorize this charge, contact us at 1-888-555-0123.", "1299.00", "USD", ["PHONE_IN_TEXT", "NEW_SENDER"], "Чек за покупку, которой не было, и телефон для «спора»."),
    ("F07", "eval_notes.json:F07", "service@pay-secure.test", "Pay Secure", "You sent a payment of 899.99 USD to Geek Squad. Not you? Call (800) 555-0147", "899.99", "USD", ["PHONE_IN_TEXT", "BRAND_IMPERSONATION", "NEW_SENDER"], "Известный бренд (Geek Squad) под несвязанным именем и телефон в тексте."),
]
for cid, origin, email, name, note, amount, cur, sigs, why in STRANGERS:
    add(f"S-{cid}", "suspicious", f"{why} Поставщик новый, истории нет.",
        inv(f"INV2-DS-{cid}", number="A-4471", amount=amount, currency=cur, note=note, source="payer_page",
            sender={"name": name, "email": email, "phone": None}, item="Subscription"),
        True, hist=None, signals=sigs, origin=origin)

sp = inv("INV2-DS-SJSON", number="A-99817", amount="530.28", currency="USD", source="payer_page", day="2026-10-17",
         note="Your subscription renews today. To cancel or dispute call our support IMMEDIATELY: +1 (555) 010-0199. Please pay to IBAN DE67100000000555555555",
         sender={"name": "Secure Protect Services LLC", "email": "support-billing@securprotect.test", "phone": None},
         items=[{"name": "Antivirus Premium 3 years", "description": None, "quantity": "1", "unitAmount": "499.00"},
                {"name": "Setup fee", "description": None, "quantity": "2", "unitAmount": "19.99"}])
add("S-SJSON", "suspicious", "Демо-счёт suspicious.json: срочный звонок, IBAN в тексте, новый поставщик.", sp, True,
    hist=None, signals=["PHONE_IN_TEXT", "SCAM_WORDING", "NEW_SENDER"], origin="suspicious.json")

# --- дубликаты: 4 ---------------------------------------------------------------------------
add("D01", "duplicate", "Тот же номер 0041, сумма, дата и текст, что у последнего счёта в истории; другой id.",
    inv("INV2-DS-D01", number="0041", note=H_NOTE, day="2026-09-28"), True, signals=["DUPLICATE_EXACT"])
add("D02", "duplicate", "Та же сумма и дата, что у последнего счёта, но другой номер 0099.",
    inv("INV2-DS-D02", number="0099", note=H_NOTE, day="2026-09-28"), True, signals=["DUPLICATE_POTENTIAL"])
add("D03", "duplicate", "Почти копия: тот же текст и позиция, сумма 36.00 вместо 35.00, дата на два дня позже.",
    inv("INV2-DS-D03", number="0043", amount="36.00", note=H_NOTE, day="2026-09-30"), True, signals=["DUPLICATE_SIMILAR"])
add("D04", "duplicate", "Не дубликат: тот же текст и сумма, но следующий месяц и следующий номер (регулярная подписка).",
    inv("INV2-DS-D04", number="0042", note=H_NOTE, day="2026-10-28"), False)

# --- смена данных поставщика: 6 -------------------------------------------------------------
NEW_IBAN = "DE67100000000555555555"
add("C01", "supplier_change", "Имя прежнее, email сменился на billing@nordhost-pay.test.",
    inv("INV2-DS-C01", note="Hosting for November.", sender={**NH, "email": "billing@nordhost-pay.test", "phone": None}),
    True, signals=["SENDER_MISMATCH"])
add("C02", "supplier_change", "Email и телефон прежние, имя сменилось на Nordhost Payments Ltd.",
    inv("INV2-DS-C02", note="Hosting for November.", sender={**NH, "name": "Nordhost Payments Ltd"}),
    True, signals=["SENDER_NAME_CHANGED"])
add("C03", "supplier_change", "Подмена домена: nordh0st.test (ноль вместо o), в тексте новый IBAN.",
    inv("INV2-DS-C03", note=f"Hosting for November. Pay to {NEW_IBAN}", sender={**NH, "email": "billing@nordh0st.test", "phone": None}),
    True, signals=["SENDER_MISMATCH"], origin="eval_notes.json:B12")
add("C04", "supplier_change", "Подмена домена: billing@nordhost.test.evil.com, в тексте новый IBAN.",
    inv("INV2-DS-C04", note=f"Hosting for November. Pay to {NEW_IBAN}", sender={**NH, "email": "billing@nordhost.test.evil.com", "phone": None}),
    True, signals=["SENDER_MISMATCH"], origin="eval_notes.json:B13")
add("C05", "supplier_change", "Поставщик прежний, но в тексте заявлена смена банка и новый IBAN (GB).",
    inv("INV2-DS-C05", note="Due to an audit our bank has changed. New IBAN: GB82WEST12345698765432"),
    True, origin="eval_notes.json:B03")
add("C06", "supplier_change", f"Поставщик прежний, в тексте старый IBAN помечен «не использовать» и дан новый {NEW_IBAN}.",
    inv("INV2-DS-C06", note=f"IBAN {IBAN} (old, do not use). Use {NEW_IBAN} instead."),
    True, origin="eval_notes.json:B05")

# --- необычные суммы: 3 ---------------------------------------------------------------------
add("U01", "unusual_amount", "Сумма 3500.00 EUR при обычных 29–36 EUR (примерно в 100 раз больше).",
    inv("INV2-DS-U01", amount="3500.00", note="Hosting for November."), True, signals=["UNUSUAL_AMOUNT"])
add("U02", "unusual_amount", "Сумма 349.00 EUR при обычных 29–36 EUR (примерно в 10 раз больше).",
    inv("INV2-DS-U02", amount="349.00", note="Hosting for November."), True, signals=["UNUSUAL_AMOUNT"])
add("U03", "unusual_amount", "Не аномалия: 41.50 EUR (+16% к среднему), объяснено изменением НДС в тексте.",
    inv("INV2-DS-U03", amount="41.50", note="Prices include 23% VAT."), False)

# --- недостаток данных: 5 -------------------------------------------------------------------
add("I01", "insufficient_data", "Только id, источник и короткий текст; ни суммы, ни поставщика. Нельзя оценить, но и подозрений нет.",
    inv("INV2-DS-I01", number=None, amount=None, currency=None, note="Thank you!", source="payer_page", account=None,
        day=None, due=None, sender=None, item=None, recipient=None),
    False, hist=None, insufficient=True, origin="eval_notes.json:L07")
add("I02", "insufficient_data", "Нет суммы, валюты и email поставщика; имя есть, текст безобидный.",
    inv("INV2-DS-I02", amount=None, currency=None, note="Hosting for November.", sender={"name": "Nordhost GmbH", "email": None, "phone": None}),
    False, insufficient=True)
add("I03", "insufficient_data", "Первый счёт нового поставщика Brightlane Studio, чистый текст: истории нет, подозрений нет.",
    inv("INV2-DS-I03", amount="120.00", note="Logo design, final payment. Thank you.", item="Logo design",
        sender={"name": "Brightlane Studio", "email": "hello@brightlane.test", "phone": None}),
    False, hist=None, insufficient=True)
add("I04", "insufficient_data", "Известный поставщик, но текст пустой (note = null): проверять нечего, подозрений нет.",
    inv("INV2-DS-I04", note=None), False, insufficient=False, origin="eval_notes.json:L06")
add("I05", "insufficient_data", "Режим standalone (accountId = null, истории нет): работают только проверки по тексту, телефон и просьба писать в WhatsApp дают подозрение.",
    inv("INV2-DS-I05", note="Write to us on WhatsApp +48 501 234 567 to cancel.", source="payer_page", account=None),
    True, hist=None, signals=["PHONE_IN_TEXT"], insufficient=True, origin="eval_notes.json:F09")

# --- проверка и запись ----------------------------------------------------------------------
ids = [c["caseId"] for c in CASES]
assert len(ids) == len(set(ids))
n = lambda cat: sum(c["category"] == cat for c in CASES)
assert 20 <= n("normal") <= 30 and 10 <= n("suspicious") <= 15, (n("normal"), n("suspicious"))
OUT.write_text(json.dumps({"schema": "dataset/1", "contractVersion": "0.6", "histories": {HIST_ID: history()},
                           "cases": CASES}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(len(CASES), "cases:", {c: n(c) for c in sorted({x['category'] for x in CASES})},
      "| flagged:", sum(c["expected"]["flagged"] for c in CASES))
