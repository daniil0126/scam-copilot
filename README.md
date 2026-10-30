# Scam Copilot

A Chrome extension (Manifest V3) that checks a PayPal invoice for signs of fraud **before you pay it**.

Fake invoices are a common scam: a genuine PayPal invoice, sent by a stranger, that asks you to call a "support number" or pays a lookalike account. Scam Copilot reads the invoice from PayPal, compares it with your history, and explains what looks wrong in plain language.

> Built for the [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/).
> A low score is not a guarantee that an invoice is safe. The score is a heuristic, not a calibrated probability of fraud.

## What it does

- **Check this invoice.** Reads the invoice ID from the open PayPal page (only when you press the button), fetches the invoice from the PayPal Invoicing API v2, and scores it.
- **Check all invoices.** Pulls every invoice of the connected PayPal account (up to 500), scores them oldest first, and shows a low / medium / high summary.
- **Findings with evidence.** For example: payment email changed, amount far from usual, phone number in the invoice text, brand impersonation, overdue date.
- **History.** Every check is stored. Re-checking an invoice updates its entry instead of duplicating it.

<!-- TODO(AI): describe the AI analysis once it is merged (what model, what it reads, what it returns). -->

### How scoring works

[`backend/app/scoring.py`](backend/app/scoring.py) compares an invoice with the earlier checks of the same supplier (matched by name and by PayPal email) and looks at the invoice text. Each finding adds points; the total maps to `low`, `medium` or `high`. One serious red flag never yields `low`.

## Architecture

```
Chrome extension (React + TS)  ──HTTP──>  FastAPI backend  ──REST──>  PayPal Invoicing API v2 (sandbox)
  content script: reads invoice ID          scoring + SQLite history
  side panel: results, history
```

| Path | Purpose |
|---|---|
| `src/` | Extension: side panel UI, content script, service worker |
| `backend/app/paypal.py` | PayPal client, invoice list and mapping |
| `backend/app/checks.py` | `POST /checks`, `POST /checks/bulk`, `GET /checks` |
| `backend/app/scoring.py` | Risk rules |
| `backend/scripts/scenarios.py` | Creates sandbox invoices for demo scenarios |
| `backend/tests/` | pytest suite (PayPal is stubbed, no network) |

## Run it

Requirements: Node 20+, Python 3.11+, Chrome, and a free [PayPal Developer](https://developer.paypal.com/) sandbox app.

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then fill PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET
uvicorn app.main:app --port 8000
```

Open <http://localhost:8000/docs> to try the API. `GET /paypal/invoices` lists the sandbox account's invoices.

Credentials come from PayPal Developer → Apps & Credentials → Sandbox → your app. Use sandbox only; never put live credentials in `.env` for a demo.

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

### 3. Demo data

Create sandbox invoices that cover the scenarios (new supplier, swapped payment email, fake Norton invoice, and so on):

```bash
cd backend
python scripts/scenarios.py --links   # creates invoices and prints their links
python scripts/scenarios.py           # creates them and checks the expected risk levels
```

Then open one of the printed links in Chrome and press **Check this PayPal invoice**, or press **Check all invoices**.

### Tests

```bash
cd backend && python -m pytest -q
npx tsc -b
```

## Known limitations

- **Whose invoices the API can see.** The Invoicing API works from the side of the account that issued the invoices. With the sandbox credentials used here the demo reads and checks invoices of that account. A payer who receives an invoice from a stranger cannot be given access to it through the app's own credentials. Supporting that path needs either user authorization through PayPal OAuth or reading the invoice from the page or PDF, and is not built yet.
- **Sandbox only.** The project has not been tested against live PayPal accounts.
- **Rule-based baseline.** The rules are hand-tuned on the demo scenarios, not on real fraud data.
- **PDF analysis** in the side panel shows clearly labelled sample data.

## License

[MIT](LICENSE)
