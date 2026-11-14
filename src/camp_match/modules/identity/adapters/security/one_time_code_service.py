"""One-time code service adapter using cryptographic secrets and hashing."""

from __future__ import annotations

import hashlib
import secrets

from camp_match.modules.identity.domain.value_objects import OneTimeCodePurpose
from camp_match.shared_kernel.domain.identifiers import EntityId


class OneTimeCodeServiceAdapter:
    def generate(self) -> str:
        """Generates a cryptographically secure 6-digit zero-padded code."""
        val = secrets.randbelow(1000000)
        return f"{val:06d}"

    def hash(self, account_id: EntityId, purpose: OneTimeCodePurpose, code: str) -> str:
        """Computes a SHA-256 hash of the account, purpose, and code."""
        raw = f"{account_id.value}:{purpose.value}:{code}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def matches(
        self,
        account_id: EntityId,
        purpose: OneTimeCodePurpose,
        code: str,
        code_hash: str,
    ) -> bool:
        """Compares a code against a stored hash in constant time."""
        computed = self.hash(account_id, purpose, code)
        return secrets.compare_digest(computed, code_hash)
