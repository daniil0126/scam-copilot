// The backend names signs by contract type (docs/plans/contracts.md, section 2). People read these labels instead.
const SIGNAL_LABELS: Record<string, string> = {
    UNUSUAL_AMOUNT: "Unusual amount",
    DUPLICATE_EXACT: "Exact duplicate",
    DUPLICATE_POTENTIAL: "Possible duplicate",
    DUPLICATE_SIMILAR: "Similar invoice",
    SENDER_MISMATCH: "Payment email changed",
    SENDER_NAME_CHANGED: "Sender name changed",
    SUSPICIOUS_LINK: "Suspicious link",
    UNUSUAL_SENDER_ACTIVITY: "Unusual sender activity",
    NEW_SENDER: "New sender",
    BRAND_IMPERSONATION: "Known brand, unrelated sender",
    PHONE_IN_TEXT: "Phone number in the text",
    SCAM_WORDING: "Pressure or scam wording",
    DUE_DATE_ISSUE: "Odd due date",
    INSUFFICIENT_DATA: "Not enough data",
}

// An unknown type (a newer backend) is shown as plain words rather than hidden.
export const signalLabel = (type: string) =>
    SIGNAL_LABELS[type] ?? (type.charAt(0) + type.slice(1).toLowerCase()).replaceAll("_", " ")
