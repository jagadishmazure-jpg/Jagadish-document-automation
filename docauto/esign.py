"""Mock e-signature: intent capture, multi-signer flow, seal + tamper check.

This is a functional mock of an e-signature provider: it records signer
intent with a timestamp and the content hash at signing time. ``seal()``
finalizes the document once all signers are done; ``verify_seal()``
detects any post-seal modification.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


class SignatureError(Exception):
    """Raised for invalid signing operations."""


@dataclass
class Signature:
    doc_id: str
    signer: str
    intent_text: str
    signed_at: str
    content_hash: str


@dataclass
class Envelope:
    doc_id: str
    signers: list[str]
    signatures: dict = field(default_factory=dict)  # signer -> Signature
    sealed: bool = False
    sealed_at: str | None = None
    sealed_checksum: str | None = None


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class SignatureService:
    def __init__(self) -> None:
        self._envelopes: dict[str, Envelope] = {}

    def request_signature(self, doc_id: str, signers: list[str]) -> Envelope:
        if not signers:
            raise SignatureError("at least one signer is required")
        if doc_id in self._envelopes:
            raise SignatureError(
                f"signature envelope already exists for '{doc_id}'")
        envelope = Envelope(doc_id=doc_id, signers=list(signers))
        self._envelopes[doc_id] = envelope
        return envelope

    def sign(self, doc_id: str, signer: str, intent_text: str,
             content: str) -> Signature:
        envelope = self._get(doc_id)
        if envelope.sealed:
            raise SignatureError(f"envelope '{doc_id}' is already sealed")
        if signer not in envelope.signers:
            raise SignatureError(
                f"'{signer}' is not a designated signer for '{doc_id}'")
        if signer in envelope.signatures:
            raise SignatureError(f"'{signer}' has already signed '{doc_id}'")
        if not intent_text.strip():
            raise SignatureError("signer intent text is required")
        signature = Signature(
            doc_id=doc_id, signer=signer, intent_text=intent_text.strip(),
            signed_at=datetime.now(timezone.utc).isoformat(),
            content_hash=_hash(content))
        envelope.signatures[signer] = signature
        return signature

    def pending(self, doc_id: str) -> list[str]:
        envelope = self._get(doc_id)
        return [s for s in envelope.signers if s not in envelope.signatures]

    def seal(self, doc_id: str, content: str) -> Envelope:
        """Finalize once every signer has signed. Records the checksum and
        locks the envelope against further signatures."""
        envelope = self._get(doc_id)
        missing = self.pending(doc_id)
        if missing:
            raise SignatureError(
                f"cannot seal '{doc_id}': awaiting {missing}")
        envelope.sealed = True
        envelope.sealed_at = datetime.now(timezone.utc).isoformat()
        envelope.sealed_checksum = _hash(content)
        return envelope

    def verify_seal(self, doc_id: str, content: str) -> bool:
        """True iff the envelope is sealed and the content is unchanged
        since sealing."""
        envelope = self._get(doc_id)
        if not envelope.sealed:
            return False
        return envelope.sealed_checksum == _hash(content)

    def _get(self, doc_id: str) -> Envelope:
        if doc_id not in self._envelopes:
            raise SignatureError(f"no envelope for doc '{doc_id}'")
        return self._envelopes[doc_id]
