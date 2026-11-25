from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, StrEnum

class SubjectKind(StrEnum):
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"
    PAYOUT = "PAYOUT"
    UNSUPPORTED = "UNSUPPORTED"

class ProviderStatusDetail(StrEnum):
    NEEDS_CUSTOMER_ACCOUNT = "NEEDS_CUSTOMER_ACCOUNT"

@dataclass(frozen=True, slots=True)
class Bank:
    code: str
    name: str

@dataclass(frozen=True, slots=True)
class ResolvedAccount:
    account_name: str

class ProviderUncertainOutcome(Exception):
    def __init__(self, provider_reference: str) -> None:
        self.provider_reference = provider_reference
        super().__init__(f"Uncertain outcome for {provider_reference}")
