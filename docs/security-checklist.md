# Security checklist — Scam Copilot

Scope: review checklist for the current backend and the AI integration. This is not a claim that every item has been verified.

## Secrets and logs
- [ ] Keep PayPal credentials, LLM API keys, webhook secrets and encryption keys only in backend `.env` / deployment secret storage.
- [ ] Confirm `.env`, private keys, database files and provider credentials are ignored by Git.
- [ ] Never log Authorization headers, cookies, access/refresh tokens, API keys, inbound secrets, full prompts or raw invoice payloads.
- [ ] Check exception paths and provider SDK errors for accidental secret or invoice-data disclosure.
- [ ] Keep logs to request IDs, event types, status codes and redacted identifiers.

## Account isolation and authorization
- [ ] Derive account identity from the authenticated backend session, never from a request body or query parameter.
- [ ] Scope every invoice, analysis, notification and report query by the authenticated account.
- [ ] Return NOT_FOUND for resources belonging to another account to avoid confirming their existence.
- [ ] Add cross-account access tests for every account-scoped endpoint.
- [ ] Do not treat a PayPal invoice ID as an authorization boundary.

## Prompt injection and AI output
- [ ] Treat invoice notes, descriptions, sender fields, links and imported email text as untrusted data, never as instructions.
- [ ] Keep trusted system instructions separate from invoice data; use explicit data delimiters.
- [ ] Send only the fields needed for the explanation; omit recipient PII, phone numbers and unrelated metadata unless necessary.
- [ ] Validate model output against a strict schema and reject malformed or unsupported values.
- [ ] Do not let AI lower the rule-based risk level or override deterministic findings.
- [ ] Do not present AI output as confirmed fraud; use “signals” and “requires verification”.
- [ ] Test injection attempts in invoice note, item description and chat history with a fake provider; assert the model output cannot change deterministic scoring.

## SSRF and untrusted URLs
- [ ] Never fetch URLs extracted from invoice notes, item descriptions, emails or paymentLinks.
- [ ] If URL reputation checks are added, use a dedicated safe-fetch design: allowlisted schemes, block private/loopback/link-local IP ranges, validate DNS results and redirects, enforce timeouts and response-size limits.
- [ ] Do not forward arbitrary user-provided URLs to internal services or cloud metadata endpoints.
- [ ] Store/display only sanitized URL metadata where possible; strip query strings and fragments from logs.

## Data minimization and retention
- [ ] Avoid storing raw email HTML or full prompts; retain only normalized fields required by the contract.
- [ ] Redact personal data in diagnostics and error reports.
- [ ] Define retention and deletion behavior for invoices, analyses, and audit logs.
- [ ] Ensure synthetic dataset fixtures never enter production bundles or real user tables.

## Operational checks
- [ ] Verify CORS origins are explicit and environment-specific.
- [ ] Apply request size limits and rate limits to chat, inbound email and webhook endpoints.
- [ ] Keep provider timeouts bounded and AI optional; rule-based checks must continue if the provider is unavailable.
- [ ] Record security-relevant events without recording secrets or full sensitive payloads.

## Findings to resolve before release
- [ ] Verify authorization/account isolation after session auth is implemented; the current legacy contract notes that older endpoints are unauthenticated.
- [ ] Verify AI context minimization and evidence validation in `backend/app/llm.py`.
- [ ] Verify tests cover prompt injection in both invoice content and chat history.
