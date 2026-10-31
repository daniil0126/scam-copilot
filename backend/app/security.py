"""Small security helpers shared by the API: who a request acts for, and keeping secrets out of the logs."""
import logging
import os
import re


def current_account() -> str:
    """The account a request acts on. It is never taken from the request body or the URL (contracts.md, Q3).

    Today there is one account: the PayPal app whose credentials the backend holds. When sessions arrive (plan 02) this
    function reads the account from the session and every route that depends on it is isolated by it already.
    """
    from app.monitor import account_id  # imported here: monitor imports the alerts, which import this module's users

    return account_id()


# --- secrets in logs --------------------------------------------------------------------------------------------

SECRET_ENV = ("PAYPAL_CLIENT_SECRET", "LLM_API_KEY", "INBOUND_EMAIL_SECRET")
REDACTED = "[redacted]"
_BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=\-]{8,}")
_PAIR = re.compile(r"(?i)\b(access_token|refresh_token|client_secret|api[_-]?key|authorization|x-inbound-secret)(\"?\s*[:=]\s*\"?)([^\s\",&]+)")


def scrub(text: str) -> str:
    """Hides the configured secrets, bearer tokens and `token=...` style pairs in a log line."""
    for name in SECRET_ENV:
        value = os.getenv(name, "")
        if len(value) >= 6:
            text = text.replace(value, REDACTED)
    text = _BEARER.sub(rf"\1{REDACTED}", text)
    return _PAIR.sub(rf"\1\2{REDACTED}", text)


def install_log_scrubber() -> None:
    """Scrubs every log record as it is created. A second call does nothing.

    A record is rewritten only when scrubbing changed it, so formatters that read `record.args` (uvicorn's access log)
    keep working for every other line. Tracebacks are not scrubbed: the code never puts a secret into an exception message,
    and tests/test_security.py checks the failure paths for that.
    """
    factory = logging.getLogRecordFactory()
    if getattr(factory, "scrubs_secrets", False):
        return

    def make_record(*args, **kwargs):
        record = factory(*args, **kwargs)
        try:
            message = record.getMessage()
            clean = scrub(message)
            if clean != message:
                record.msg, record.args = clean, ()
        except Exception:  # logging must never be the thing that fails
            pass
        return record

    make_record.scrubs_secrets = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(make_record)
