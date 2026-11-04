# Scam Copilot

A Chrome extension (Manifest V3) that checks a PayPal invoice for signs of fraud **before you pay it**.

Fake invoices are a common scam: a genuine PayPal invoice, sent by a stranger, that asks you to call a "support number" or pays a lookalike account. Scam Copilot reads the invoice, compares it with the supplier's history, and explains what looks wrong in plain language.

> Built for the [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/).
> A low score is not a guarantee that an invoice is safe. The score is a heuristic, not a calibrated probability of fraud.

## Try it (hosted copy, no build)

A copy of the backend runs on Render, on the **PayPal Sandbox only**, so you can try the extension without installing anything but the extension itself.

1. Download `scam-copilot-extension.zip` from the [latest release](https://github.com/daniil0126/scam-copilot/releases/latest) and unzip it.
2. In Chrome open `chrome://extensions`, turn on **Developer mode**, press **Load unpacked** and pick the unzipped folder. Pin the extension and click its icon: the side panel opens.
3. Open one of the demo invoices (links are in the *Testing instructions* of the Devpost submission) and press **Check this PayPal invoice**.

The hosted backend sleeps when idle on Render's free plan: the first call after a pause can take up to a minute (open `<hosted url>/health` once to wake it). It shows the account's own Sandbox invoices; nothing here touches real money. To run everything yourself instead, follow the sections below.

## What it does

Three ways to get an invoice into a check:

- **Invoice you received (payer page).** Open the invoice page PayPal shows to the payer (`/invoice/p/…`) and press **Check this PayPal invoice**. The extension reads the visible text of that page, only when you press the button, and the backend turns it into invoice fields. PayPal's API does not return invoices issued by other accounts (it answers `403 NOT_AUTHORIZED`), so this is how an invoice from a stranger is checked.
- **Invoice of the connected account (PayPal Invoicing API v2).** The backend lists and loads the invoices of the PayPal account whose sandbox credentials it holds: paginated list, creation-date window through `search-invoices`, one request per invoice for the details, retries with backoff on rate limits and server errors.

- **Webhooks (own invoices, optional).** With `PAYPAL_WEBHOOK_ID` set, `POST /webhooks/paypal` takes PayPal's invoice events. The signature is verified with PayPal, only the invoice id is taken from the event, and the invoice is read from PayPal and goes through the same pipeline as polling, so a change shows up in seconds instead of at the next poll. Events are a hint, not data: they arrive in batches, out of order and with the invoice as of delivery time. The same version is stored once. Polling stays on for events that never arrive. Only the issuer's app receives these events; a payer gets none, which is why the payer side reads emails. Needs a public HTTPS address.
- **Invoice emails.** PayPal emails the payer when an invoice is issued and again when it is changed. `POST /inbound/email` takes the HTML of such an email, reads it and checks it: where its links lead, and what changed since the earlier email of the same invoice (amount, due date, items). When the payer page of that invoice is checked afterwards, it is compared with the emails. That is how a note changed after sending is found: PayPal's update email leaves the note out. The extension needs no setup for this: open the email in the Developer Dashboard (Sandbox notifications) and press **Check this email**; only the email block is read, and only on that press (the backend accepts the extension by the origin the browser attaches, which a web page cannot fake). Any other sender, such as a mail filter forwarding emails, must send `INBOUND_EMAIL_SECRET` in the `X-Inbound-Secret` header. The result says what it was checked from, groups the findings (needs attention / not checked / passed) and compares against the earlier email. Sending the same email again judges it afresh with the current rules; no second copy is stored.

Around the checks, on the backend:

- **Alerts.** Each stored invoice version can raise one in-app alert (critical or high risk, potential duplicate, vendor impersonation, suspicious payment link). `GET /notifications`, `GET /notifications/unread-count`, `GET/PUT /monitoring/settings` (threshold and categories). Wording is "signs found", never "fraud".
- **Monthly report.** `GET/POST /reports/monthly?month=YYYY-MM` and `GET /monitoring/summary`, counted by SQL from the stored analyses; an empty month says so.
- **AI guard.** Only minimised data goes to the model, invoice text is passed as data, and values in its answer that are not in the input are dropped. The model never changes the score. `backend/scripts/evaluate.py` measures Precision, Recall and FPR on the 59-case set in `backend/tests/dataset/`; the figures are not recorded yet.
- **Tables (AG Grid Community).** Monitor events (new rows appear by themselves and flash), Alerts, the report's "worth a manual look" list and History are AG Grid tables: sort, column filters, a quick filter and CSV export of what is shown (cells that start with `=`, `+`, `-` or `@` are quoted against spreadsheet formulas). Community edition only, no Enterprise features.
- **Security.** Secrets are scrubbed from logs; checklist in `docs/plans/security-checklist.md`.

Either way the invoice is scored and every finding carries its evidence:

- payment email changed, amount far from usual, same PayPal email under a new name;
- a phone number or scam wording in the invoice text, a known brand under an unrelated name, an overdue date.

The payer page parser also extracts the business behind a "doing business as" name (the page says "Invoice issued by X (doing business as Y)"), but no rule uses it yet.

Every check is stored in the **History** table (AG Grid). Checking the same invoice again updates its entry instead of duplicating it.

### AI

The backend has an optional LLM layer (`backend/app/llm.py`): the invoice text is sent as delimited data and never as instructions, the answer is validated, and a failing model never breaks a check. With `LLM_PROVIDER` empty (the default) everything runs on the rules alone and the "AI review" block does not appear. The same layer powers the question-and-answer chat about a checked invoice.

`LLM_PROVIDER=openrouter` (`backend/app/llm_openrouter.py`) uses OpenRouter and **free models only**: `LLM_MODEL` must end in `:free` (several can be listed, comma-separated: when one is rate-limited, failing or withdrawn, the next is tried, and each is price-checked on its own), and before the first call OpenRouter must list the model with a zero price. If either fails, or the price cannot be read, the provider refuses to start and checks run on rules alone. Free models can be rate limited by their host at any time, and the free tier may use prompts for training, so do not send real invoices through it.

**Reading PayPal from the chat.** With a model that supports tool calls, the chat can read the connected Sandbox account through the [PayPal Agent Toolkit](https://github.com/paypal/agent-toolkit) (`@paypal/mcp`, started per call with `--tools=invoices.list,invoices.get`). Exactly two read-only tools are available, `list_invoices` and `get_invoice`; a test fails if any other name appears. The model gets a few fields with emails masked and phone numbers removed, inside a `<tool_data>` block it is told to treat as data, and its answer goes through the same checks as any chat answer. The reply says which tools were used. It sees only invoices the connected account issued, not those a payer received. If Node, the keys or a tool-capable model are missing, or PayPal fails, the chat answers as before without tools. Setup: Node 20+, then `cd backend/mcp && npm ci --ignore-scripts` (versions are pinned by the lockfile).

<!-- TODO(AI): the effect of the model on an evaluation set is not measured yet. In one live check it flagged a planted "ignore previous instructions" line, but it also invented a doubtful finding, and its findings can still raise the risk level. -->

### How scoring works

[`backend/app/scoring.py`](backend/app/scoring.py) compares an invoice with the earlier checks of the same supplier (matched by name and by PayPal email) and looks at the invoice text. Each finding adds points; the total maps to `low`, `medium` or `high`. One serious red flag never yields `low`. Missing data is not guessed: a field the page or the API did not show stays empty.

## Architecture

```
Chrome extension (React + TS) ──HTTP──> FastAPI backend ──REST──> PayPal Invoicing API v2 (sandbox)
  content script: invoice page text        normalization + scoring + SQLite history
  side panel: result, History (AG Grid), Monitor (live state, alerts, monthly report), Settings (alert rules)
```

| Path | Purpose |
|---|---|
| `src/` | Extension: side panel UI, content script, service worker |
| `backend/app/paypal.py` | PayPal client: token, paginated list, date window, typed errors, retries |
| `backend/app/normalize.py` | PayPal response and payer page text to one `Invoice` shape |
| `backend/app/payer_page.py` | Reads the text of a payer page (built and tested on real sandbox pages) |
| `backend/app/checks.py` | `POST /checks`, `POST /checks/page`, `POST /checks/bulk`, `GET /checks` |
| `backend/app/scoring.py` | Risk rules |
| `backend/app/llm.py`, `llm_openrouter.py`, `chat.py` | Optional LLM layer, free-only OpenRouter provider, chat |
| `backend/app/webhooks.py` | `POST /webhooks/paypal`: verified signal that an invoice changed; the invoice is then read from PayPal |
| `backend/app/email_invoice.py`, `email_rules.py`, `inbound.py` | Invoice emails: parser, rules on links and changes, `POST /inbound/email` |
| `backend/scripts/scenarios.py` | Creates sandbox invoices for demo scenarios |
| `backend/tests/` | pytest suite (PayPal is stubbed, no network; fixtures are sandbox data only) |
| `docs/plans/` | Design notes, data contracts and decision records (`adr/`) |

## Run it

Requirements: Node 20+, **Python 3.13** (developed on it; `backend/.python-version` pins it). 3.14 also installs and passes the tests on macOS, and every pinned package has a prebuilt Windows build for it; if `pip install` still tries to compile something, upgrade pip first (`python -m pip install -U pip`) or use 3.13, Chrome, and a free [PayPal Developer](https://developer.paypal.com/) sandbox app with the **Invoicing** feature enabled.

### 1. Backend

```bash
cd backend
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then fill PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET
uvicorn app.main:app --port 8000
```

On Windows (PowerShell) use `py -3.13 -m venv .venv`, `.venv\Scripts\activate` and `Copy-Item .env.example .env` instead of the `venv` and `cp` lines above.

Optional in `backend/.env`: `PAYPAL_WEBHOOK_ID` turns on `POST /webhooks/paypal`; `INBOUND_EMAIL_SECRET` lets senders other than the extension use `POST /inbound/email` (header `X-Inbound-Secret`; the extension itself needs no secret); `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` turn on the AI layer (see above). Use a separate OpenRouter key with a low credit limit.

Open <http://localhost:8000/docs> to try the API. `GET /paypal/invoices` lists the sandbox account's invoices; `GET /health` should answer `{"status": "ok"}`.

Credentials come from PayPal Developer → Apps & Credentials → Sandbox → your app. Use sandbox only; never put live credentials in `.env` for a demo. No credentials are stored in this repository.

### 2. Extension

```bash
npm ci
npm run build
```

1. Open `chrome://extensions` and enable **Developer mode**.
2. Click **Load unpacked** and select the `dist/` folder.
3. The extension ID is fixed by the `key` in `public/manifest.json` (`hjkgljmknkdiikgaflofnlmhbjjjilob`), which is what `PROJECT_ID` in `.env.example` holds. The backend only accepts requests from that origin.
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
- **Webhooks are not used yet.** In our Sandbox tests PayPal sent invoice events only to the app of the account that issues the invoice, never to the recipient. An event carries the invoice as it is when delivered, not as it was at the event, and events can arrive out of order. There is no event for sending. The monitor polls instead.
- **Invoice emails.** Sandbox emails are not delivered to a mailbox, only shown in the Developer Dashboard, so the email path is tested on saved emails; the layout of real PayPal emails is not tested. The update email omits the seller's note, and no email shows the issuer's email or phone. A forwarded email loses its sender authentication, so only its content and links are judged.
- **Sandbox only.** The project has not been tested against live PayPal accounts.
- **Rule-based baseline.** The rules are hand-tuned on demo scenarios, not on real fraud data.
- **No PDF upload.** Invoices are read from PayPal's API, the payer page and PayPal's invoice emails; a PDF file is not analysed.

## How scoring works

An invoice is scored by one of two engines, chosen by the `RULES_ENGINE` environment variable (see `.env.example`):

- **`v1` (unset or `v1`, the default):** `app/scoring.py`, a flat rule list with fixed points (`PHONE=35`,
  `SCAM_WORDS=20`, `payee change=60`, and so on). This is the engine the demo and the Devpost text describe.
- **`v2`:** `app/rules/`, a rule engine that turns each sign into a typed `Signal` and combines signals by family
  with decay. It needs vendor history from `build_vendor_history(db, account, invoice)` and runs through the same
  `run_check` pipeline (`app/checks.py`, `app/monitor.py`, `app/inbound.py`).

Both engines write the same shape of result to `checks.result`. A v2 result carries the legacy fields
(`level`, `score`, `findings`, `recommendation`) **and** the contract fields (`riskLevel`, `riskScore`,
`signals`, `confidence`), so alerts, reports, the AI explanation and the extension do not need to know which
engine ran. Switching `RULES_ENGINE` does not change any API shape.

### Signals and levels

A v2 signal has a type (`PHONE_IN_TEXT`, `SENDER_MISMATCH`, `DUPLICATE_EXACT`, …), a severity
(`LOW` / `MEDIUM` / `HIGH` / `CRITICAL`) and a status (`DETECTED` or `INSUFFICIENT_DATA`). Signals are grouped
into six families — `amount`, `duplicates`, `vendor_identity`, `links`, `activity`, `textual` — and the score of
a family is `max + decay × second + decay² × third + …`. The total is capped at 100 and mapped to a level:

| score | level |
|---|---|
| 0–29 | LOW |
| 30–59 | MEDIUM |
| 60–79 | HIGH |
| 80–100 | CRITICAL |

The current calibration (`rules/config.py`, `rules/aggregator.py`) puts every family at weight 40 and
`family_decay` at 0.5, so one HIGH signal in any family scores 40 (MEDIUM) and two HIGH signals in the same
family score 60 (HIGH). `SEVERITY_POINTS["MEDIUM"]` is 30, so one MEDIUM signal reaches the MEDIUM band on its
own; `NEW_SENDER` and `DUE_DATE_ISSUE` are LOW on purpose, because being new or having no due date is a fact,
not a risk.

`confidence` is about data completeness, not severity: it is LOW when the history is truncated, three or more
fields are missing, or there is no history at all; HIGH when at most one field is missing and the history has
at least `confidence_history_full_min` prior invoices. A rule that cannot run reports `INSUFFICIENT_DATA`
instead of guessing; those signals are neither a pass nor a risk and the panel shows them apart.

### Numbers and where they come from

`scripts/compare_engines.py` runs both engines on `tests/dataset/cases.json` (59 labelled cases) and on the
seven demo scenarios reconstructed from `scripts/scenarios.py`, and writes `docs/plans/engine-comparison.md`.
Calibrated numbers on the dataset, with "flagged" at HIGH and above (the alert threshold):

| engine | Precision | Recall | FPR |
|---|---|---|---|
| legacy (`scoring.score_invoice`) | 72.7% | 32.0% | 8.8% |
| engine (`rules.engine.evaluate`, calibrated) | 100.0% | 32.0% | 0.0% |

At MEDIUM and above (the dataset's own `expected.flagged`): legacy P=57.1% R=64.0% FPR=35.3%; engine P=59.3%
R=64.0% FPR=32.4%.

The full report, including every case where the two engines disagree and why, is in
`docs/plans/engine-comparison.md`. In short:

**Where the engine is better than legacy:** a changed sender email (`C01`) and a changed sender name on the same
account (`C02`) are flagged by the engine and missed by legacy, because the engine compares the sender against
the whole history. A link to the supplier's own domain (`N28`) is LOW on the engine and MEDIUM on legacy. A ×100
amount (`U01`) is HIGH on the engine and MEDIUM on legacy.

**What is not fixed yet, and why:** `rule_d` does not treat `http://` links or generic `*-pay.example` hosts as
suspicious (`S-TF02`, `S-HF02`); `SCAM_WORDS` matches ordinary words such as "auto-renewal" and "subscription"
(`N05`, `N10`, `N23`). Both are rule changes (`rule_*.py`), out of scope for the current sprint.

### Why `v1` is still the default

The freeze is about not changing the default behaviour, and the demo and the Devpost text describe the legacy
scorer. `RULES_ENGINE=v2` is available for a reviewer and is tested end to end
(`tests/test_checks_engine_v2.py`, and `test_monitor.py` / `test_inbound.py` also pass with `RULES_ENGINE=v2`).
Switching is a one-line `.env` change and does not change any API shape.

### Thresholds are initial values

The numbers in `rules/config.py` are calibrated on `tests/dataset/cases.json` (see
`docs/plans/engine-comparison.md` and `docs/plans/calibration-sweep.md` when it exists), not on production
traffic. They are a starting point, not a final answer: a new labelled batch should be run through
`scripts/compare_engines.py` before they are considered final.

## Hosting a copy (maintainers)

`render.yaml` is a Render Blueprint for the backend (Docker, `backend/Dockerfile`; Node is included because the PayPal Agent Toolkit is a Node program).

1. On Render choose *New → Blueprint*, point it at this repository, and fill the secrets it asks for: `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` (Sandbox app keys), `ACCESS_TOKEN` (any long random string; every call must send it in `X-Access-Token`), and optionally `LLM_API_KEY` (a free-tier OpenRouter key). Leave `LLM_PROVIDER` empty to run on the rules alone.
2. Wait for `https://<service>.onrender.com/health` to answer `{"status":"ok"}`. The database is rebuilt from PayPal's last 30 days on every fresh start (the free plan has no persistent disk).
3. Build the extension for it: `API_URL=https://<service>.onrender.com ACCESS_TOKEN=<same value> sh scripts/build-release.sh`. The zip lands in `release/scam-copilot-extension.zip`; attach it to a GitHub Release.

The token is inside the zip, so it keeps strangers and scanners off the API; it is not a user login. Rotate the Sandbox keys and the token when judging ends.

## License

[MIT](LICENSE)
