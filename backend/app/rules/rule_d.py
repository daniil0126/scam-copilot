from __future__ import annotations

import re
from urllib.parse import urlparse

from .config import RulesConfig
from .types import Invoice, Signal, VendorHistory


RULE_VERSION_SUFFIX = "links"

KNOWN_BRANDS = (
    "paypal", "apple", "microsoft", "amazon", "google",
    "netflix", "norton", "mcafee", "geeksquad", "bestbuy",
    "walmart", "lifelock", "avast",
)

OFFICIAL_DOMAINS = {
    "paypal": {"paypal.com"},
    "apple": {"apple.com", "icloud.com"},
    "microsoft": {"microsoft.com", "live.com", "office.com", "outlook.com"},
    "amazon": {"amazon.com", "amazon.co.uk", "amazon.de"},
    "google": {"google.com", "gmail.com"},
    "netflix": {"netflix.com"},
}

IP_HOST = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
PUNYCODE_PREFIX = "xn--"


def _host(url: str) -> str | None:
    try:
        parsed = urlparse(url if "://" in url else f"http://{url}")
    except ValueError:
        return None
    return parsed.hostname.lower() if parsed.hostname else None


def _subdomain_depth(host: str) -> int:
    return max(0, len(host.split(".")) - 2)


def _brand_in_foreign_domain(host: str) -> str | None:
    for brand, official in OFFICIAL_DOMAINS.items():
        if brand not in host:
            continue
        if any(host == d or host.endswith("." + d) for d in official):
            return None
        return brand
    return None


def _classify(url: str, config: RulesConfig) -> tuple[str, dict] | None:
    host = _host(url)
    if host is None:
        return None
    if IP_HOST.match(host):
        return "ip_host", {"url": url, "host": host, "reason": "ip_host"}
    if any(part.startswith(PUNYCODE_PREFIX) for part in host.split(".")):
        return "punycode", {"url": url, "host": host, "reason": "punycode"}
    depth = _subdomain_depth(host)
    if depth > config.link_max_subdomain_depth:
        return "deep_subdomain", {"url": url, "host": host, "reason": "deep_subdomain", "depth": depth}
    brand = _brand_in_foreign_domain(host)
    if brand:
        return "brand_foreign_domain", {"url": url, "host": host, "reason": "brand_foreign_domain", "brand": brand}
    return None


def rule_d(invoice: Invoice, history: VendorHistory, config: RulesConfig) -> list[Signal]:
    rule_version = f"{RULE_VERSION_SUFFIX}-{config.version}"
    if not invoice.paymentLinks:
        return []
    signals: list[Signal] = []
    for url in invoice.paymentLinks:
        hit = _classify(url, config)
        if hit is None:
            continue
        reason, data = hit
        signals.append(Signal(
            type="SUSPICIOUS_LINK",
            severity="HIGH" if reason == "brand_foreign_domain" else "MEDIUM",
            status="DETECTED",
            evidence=f"{url} — {reason}",
            evidenceData=data,
            source="RULE_ENGINE",
            ruleVersion=rule_version,
        ))
    return signals