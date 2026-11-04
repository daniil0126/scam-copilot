from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


# --- Literals ---

SignalType = Literal[
    "UNUSUAL_AMOUNT", "DUPLICATE_EXACT", "DUPLICATE_POTENTIAL", "DUPLICATE_SIMILAR",
    "SENDER_MISMATCH", "SENDER_NAME_CHANGED", "SUSPICIOUS_LINK", "UNUSUAL_SENDER_ACTIVITY",
    "NEW_SENDER", "BRAND_IMPERSONATION", "PHONE_IN_TEXT", "SCAM_WORDING", "DUE_DATE_ISSUE",
]

Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
SignalStatus = Literal["DETECTED", "INSUFFICIENT_DATA"]
SignalSource = Literal["API", "RULE_ENGINE", "AI"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Confidence = Literal["LOW", "MEDIUM", "HIGH"]


# --- Сигнал ---

class Signal(BaseModel):
    type: SignalType
    severity: Severity
    status: SignalStatus
    evidence: str
    evidenceData: dict = Field(default_factory=dict)
    source: SignalSource
    ruleVersion: str

    @model_validator(mode="after")
    def _evidence_required_when_detected(self) -> "Signal":
        if self.status == "DETECTED" and not self.evidence.strip():
            raise ValueError("DETECTED signal must have non-empty evidence")
        return self


# --- Инвойс ---

class InvoiceItem(BaseModel):
    name: str | None = None
    description: str | None = None
    quantity: str | None = None
    unitAmount: str | None = None


class Invoice(BaseModel):
    id: str
    accountId: str | None = None
    # "email" added: normalize_email() produces source="email" and the rule engine must accept it
    # (docs/plans/contracts.md, section 1). The rules themselves do not care where the invoice came from.
    source: Literal["paypal_api", "payer_page", "email", "pdf"]
    invoiceNumber: str | None = None
    status: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    invoiceDate: date | None = None
    dueDate: date | None = None
    senderName: str | None = None
    senderLegalName: str | None = None
    senderEmail: str | None = None
    senderPhone: str | None = None
    recipientName: str | None = None
    recipientEmail: str | None = None
    paymentTerms: str | None = None
    items: list[InvoiceItem] | None = None
    paymentLinks: list[str] | None = None
    note: str | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None
    contentHash: str


# --- История поставщика (готовит Даниил, потребляет Адиль) ---

class HistoricalInvoice(BaseModel):
    id: str
    invoiceNumber: str | None = None
    amount: str | None = None
    currency: str | None = None
    createdAt: datetime | None = None
    itemsSignature: str | None = None
    senderEmail: str | None = None
    senderName: str | None = None
    paymentLinks: list[str] | None = None


class ContactSnapshot(BaseModel):
    email: str | None = None
    name: str | None = None
    phone: str | None = None
    firstSeen: datetime | None = None
    lastSeen: datetime | None = None


class VendorHistory(BaseModel):
    senderKey: str
    priorInvoices: list[HistoricalInvoice] = Field(default_factory=list)
    knownContacts: list[ContactSnapshot] = Field(default_factory=list)
    otherSenderInvoices: list[HistoricalInvoice] = Field(default_factory=list)
    totalCount: int = 0
    complete: bool = True


# --- Результат оценки ---

class ComparisonRow(BaseModel):
    field: str
    current: str | None = None
    previous: str | None = None
    differs: bool


class RiskResult(BaseModel):
    invoiceId: str
    invoiceVersionHash: str
    riskScore: int
    riskLevel: RiskLevel
    confidence: Confidence
    signals: list[Signal] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    comparison: list[ComparisonRow] = Field(default_factory=list)
    engineVersion: str
    analyzedAt: datetime
    ai: dict | None = None