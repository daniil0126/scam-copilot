# Scam Copilot

A Chrome extension (Manifest V3) that checks a PayPal invoice for signs of fraud **before you pay it**.

Fake invoices are a common scam: a genuine PayPal invoice, sent by a stranger, that asks you to call a "support number" or pays a lookalike account. Scam Copilot reads the invoice, compares it with the supplier's history, and explains what looks wrong in plain language.

> Built for the [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/).
> A low score is not a guarantee that an invoice is safe. The score is a heuristic, not a calibrated probability of fraud.

## What it does

Two ways to get an invoice into a check:

- **Invoice you received (payer page).** Open the invoice page PayPal shows to the payer (`/invoice/p/…`) and press **Check this PayPal invoice**. The extension reads the visible text of that page, only when you press the button, and the backend turns it into invoice fields. PayPal's API does not return invoices issued by other accounts (it answers `403 NOT_AUTHORIZED`), so this is how an invoice from a stranger is checked.
- **Invoice of the connected account (PayPal Invoicing API v2).** The backend lists and loads the invoices of the PayPal account whose sandbox credentials it holds: paginated list, creation-date window through `search-invoices`, one request per invoice for the details, retries with backoff on rate limits and server errors.

Either way the invoice is scored and every finding carries its evidence:

- payment email changed, amount far from usual, same PayPal email under a new name;
- a phone number or scam wording in the invoice text, a known brand under an unrelated name, an overdue date.

The payer page parser also extracts the business behind a "doing business as" name (the page says "Invoice issued by X (doing business as Y)"), but no rule uses it yet.

Every check is stored in the **History** table (AG Grid). Checking the same invoice again updates its entry instead of duplicating it.

### AI

The backend has an optional LLM layer (`backend/app/llm.py`): the invoice text is sent as delimited data and never as instructions, the answer is validated, and a failing model never breaks a check. **No model is bundled yet: with `LLM_PROVIDER` empty (the default) everything runs on the rules alone** and the "AI review" block simply does not appear. The same layer powers the question-and-answer chat about a checked invoice.

<!-- TODO(AI): replace this section once a provider is merged: model, what it reads, what it returns, measured effect on the evaluation set. -->

### How scoring works

[`backend/app/scoring.py`](backend/app/scoring.py) compares an invoice with the earlier checks of the same supplier (matched by name and by PayPal email) and looks at the invoice text. Each finding adds points; the total maps to `low`, `medium` or `high`. One serious red flag never yields `low`. Missing data is not guessed: a field the page or the API did not show stays empty.

## Architecture

```
Chrome extension (React + TS) ──HTTP──> FastAPI backend ──REST──> PayPal Invoicing API v2 (sandbox)
  content script: invoice page text        normalization + scoring + SQLite history
  side panel: result, History (AG Grid)
```

| Path | Purpose |
|---|---|
| `src/` | Extension: side panel UI, content script, service worker |
| `backend/app/paypal.py` | PayPal client: token, paginated list, date window, typed errors, retries |
| `backend/app/normalize.py` | PayPal response and payer page text to one `Invoice` shape |
| `backend/app/payer_page.py` | Reads the text of a payer page (built and tested on real sandbox pages) |
| `backend/app/checks.py` | `POST /checks`, `POST /checks/page`, `POST /checks/bulk`, `GET /checks` |
| `backend/app/scoring.py` | Risk rules |
| `backend/app/llm.py`, `chat.py` | Optional LLM layer and chat |
| `backend/scripts/scenarios.py` | Creates sandbox invoices for demo scenarios |
| `backend/tests/` | pytest suite (PayPal is stubbed, no network; fixtures are sandbox data only) |
| `docs/plans/` | Design notes, data contracts and decision records (`adr/`) |

## Run it

Requirements: Node 20+, Python 3.11+, Chrome, and a free [PayPal Developer](https://developer.paypal.com/) sandbox app with the **Invoicing** feature enabled.

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then fill PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET
uvicorn app.main:app --port 8000
```

Open <http://localhost:8000/docs> to try the API. `GET /paypal/invoices` lists the sandbox account's invoices; `GET /health` should answer `{"status": "ok"}`.

Credentials come from PayPal Developer → Apps & Credentials → Sandbox → your app. Use sandbox only; never put live credentials in `.env` for a demo. No credentials are stored in this repository.

### 2. Extension

```bash
npm install
npm run build
```

1. Open `chrome://extensions` and enable **Developer mode**.
2. Click **Load unpacked** and select the `dist/` folder.
3. The extension ID is fixed by the `key` in `public/manifest.json` (`cofihcnoeiipgcppdollgpalapkalkem`), which is what `PROJECT_ID` in `.env.example` holds. The backend only accepts requests from that origin.
4. Click the Scam Copilot icon to open the side panel.

The UI can also run on its own for development: `npm run dev`. Page reading only works inside the extension.

### 3. Try it on sandbox invoices

1. In the PayPal Developer dashboard use (or create) a sandbox **business** account for the issuer and a sandbox **personal** account for the payer.
2. Create and send an invoice from the business account to the personal account (in the sandbox PayPal UI, or with `POST /paypal/sandbox/invoices` and then `POST /paypal/sandbox/invoices/{id}/send` on the running backend). PayPal sends only invoices whose issuer is a real sandbox account.
3. Open the invoice as the payer. The payer page address is `https://www.sandbox.paypal.com/invoice/p/#<id>`; for an invoice you issued it is also the `detail.metadata.recipient_view_url` of `GET /v2/invoicing/invoices/{id}`.
4. Open the side panel and press **Check this PayPal invoice**.

`backend/scripts/scenarios.py` creates a set of draft invoices that cover the rule scenarios (new supplier, swapped payment email, a subscription "renewal" with a phone number, and so on). The recipient defaults to a sandbox address of the authors; set `SANDBOX_RECIPIENT` to your own personal sandbox email.

```bash
cd backend
python scripts/scenarios.py --links   # creates the invoices and prints their links
python scripts/scenarios.py           # creates them and checks the expected risk levels
```

### Tests

```bash
cd backend && python -m pytest -q
npx tsc -b
```

## Known limitations

- **Whose invoices the API can see.** The Invoicing API works from the side of the account that issued the invoices. With the credentials of one sandbox app it returns that account's invoices only; an invoice issued by someone else answers `403`. Checking those goes through the payer page text instead.
- **No user sign-in with PayPal for reading invoices.** We tried Log in with PayPal in the sandbox: it rejects the invoicing scope (`invalid scope`), and a user token granted with `openid email` gets `403` on the invoice list. Letting arbitrary users connect their own accounts would need PayPal's partner access, which its documentation describes as available to select partners only. Not built.
- **The payer page is read as displayed.** The parser was built on three real sandbox pages. It does not show the issuer's phone number, and often not the issuer's email, so rules that depend on them cannot fire on that path. Paid, cancelled and non-USD invoices have not been seen yet.
- **Sandbox only.** The project has not been tested against live PayPal accounts.
- **Rule-based baseline.** The rules are hand-tuned on demo scenarios, not on real fraud data.
- **PDF analysis** in the side panel shows clearly labelled sample data.

## License

[MIT](LICENSE)
