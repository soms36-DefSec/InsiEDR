from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class DecryptResult:
    payload: dict[str, Any]
    integrity_ok: bool
    plugin_used: str


class BaseCryptoPlugin(ABC):
    name: str = "base"
    version: str = "0.0.0"
    enabled: bool = True

    @abstractmethod
    def encrypt(self, payload_bytes: bytes, key: bytes) -> bytes:
        raise NotImplementedError()

    @abstractmethod
    def decrypt(self, ciphertext: bytes, key: bytes) -> DecryptResult:
        raise NotImplementedError()

    @abstractmethod
    def can_handle(self, header_hint: str) -> bool:
        raise NotImplementedError()
