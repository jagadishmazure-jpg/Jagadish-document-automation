"""Intelligent document processing: classify + extract fields.

Deterministic keyword + structure rules — no ML model needed. Every
extracted field carries a confidence score and the source snippet it
came from.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DOC_TYPES = ("invoice", "contract", "receipt", "policy", "memo")

_TYPE_SIGNALS: dict[str, list[str]] = {
    "invoice": ["invoice", "invoice no", "bill to", "amount due", "payment terms",
                "line item", "subtotal", "tax id"],
    "contract": ["agreement", "hereby agree", "terms and conditions", "party a",
                 "party b", "effective date", "termination", "governing law",
                 "signatures", "whereas"],
    "receipt": ["receipt", "cashier", "change due", "thank you for shopping",
                "transaction id", "payment method"],
    "policy": ["policy", "purpose", "scope", "all employees must", "compliance",
               "effective immediately", "procedure"],
    "memo": ["memo", "to:", "from:", "subject:", "regarding"],
}

_AMOUNT_RE = re.compile(r"\$?\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+\.\d{2})")
_DATE_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4})\b",
    re.IGNORECASE)
_PARTY_RE = re.compile(
    r"\b([A-Z][A-Za-z&'.]*(?:\s+[A-Z][A-Za-z&'.]*){0,3}\s+"
    r"(?:Inc|LLC|Ltd|Corp|Corporation|Company|Co|GmbH|Pvt))\b")


@dataclass
class Field:
    name: str
    value: str
    confidence: float
    source: str


@dataclass
class Classification:
    doc_type: str
    confidence: float
    signals: list[str] = field(default_factory=list)


def classify(content: str) -> Classification:
    """Score each doc type by signal hits; return the best, or memo as a
    neutral fallback with low confidence when nothing matches."""
    lowered = content.lower()
    scored = []
    for doc_type, signals in _TYPE_SIGNALS.items():
        hits = [s for s in signals if s in lowered]
        scored.append((doc_type, hits))
    scored.sort(key=lambda item: len(item[1]), reverse=True)
    best_type, hits = scored[0]
    if not hits:
        return Classification(doc_type="memo", confidence=0.2, signals=[])
    confidence = min(0.95, 0.4 + 0.1 * len(hits))
    return Classification(doc_type=best_type, confidence=confidence,
                          signals=hits)


def _snippet(content: str, match: re.Match, radius: int = 30) -> str:
    start = max(0, match.start() - radius)
    end = min(len(content), match.end() + radius)
    return content[start:end].strip()


def extract_fields(content: str, doc_type: str) -> list[Field]:
    """Extract amounts, dates, parties. Field set is fixed per doc type so
    callers get a predictable shape."""
    fields: list[Field] = []

    amounts = list(_AMOUNT_RE.finditer(content))
    if amounts and doc_type in ("invoice", "receipt", "contract"):
        # Largest amount is usually the total.
        best = max(amounts, key=lambda m: float(m.group(1).replace(",", "")))
        fields.append(Field(
            name="total_amount", value=best.group(1).replace(",", ""),
            confidence=0.85, source=_snippet(content, best)))

    dates = list(_DATE_RE.finditer(content))
    if dates:
        first = dates[0]
        fields.append(Field(name="document_date", value=first.group(1),
                            confidence=0.8, source=_snippet(content, first)))

    parties = list(_PARTY_RE.finditer(content))
    seen: set[str] = set()
    for match in parties:
        name = " ".join(match.group(1).split())
        if name not in seen:
            seen.add(name)
            fields.append(Field(name="party", value=name, confidence=0.75,
                                source=_snippet(content, match)))
        if len([f for f in fields if f.name == "party"]) >= 2:
            break

    if doc_type == "contract":
        term = re.search(r"term[:\s]+(\d+)\s*(months?|years?)", content,
                         re.IGNORECASE)
        if term:
            fields.append(Field(name="contract_term",
                                value=f"{term.group(1)} {term.group(2)}",
                                confidence=0.8,
                                source=_snippet(content, term)))
    return fields
