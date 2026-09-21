from __future__ import annotations

from typing import Dict

from server.config import config

from server.crypto.aesgcm_plugin import AESGCMPlugin
from server.crypto.hpke_plugin import HPKEPlugin
from server.crypto.plaintext_plugin import PlaintextPlugin
from server.crypto.fernet_plugin import FernetPlugin


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: Dict[str, object] = {}

    def initialize(self) -> None:
        self._plugins.clear()
        # Initialize HPKE plugin if keys are configured
        try:
            hpke_keys = config.load_hpke_private_keys()
            if hpke_keys:
                self._plugins[HPKEPlugin.scheme] = HPKEPlugin(hpke_keys, default_key_id=config.hpke_key_id)
        except Exception:
            pass
        # Initialize AES-GCM plugin if key is available
        try:
            key = config.load_aes_key()
            self._plugins[AESGCMPlugin.scheme] = AESGCMPlugin(key)
        except Exception:
            # If no key configured, do not fail import but leave plugin out
            pass
        # Initialize Fernet only when explicitly enabled.
        if config.enable_fernet:
            try:
                fkey = config.load_fernet_key()
                self._plugins[FernetPlugin.scheme] = FernetPlugin(fkey)
            except Exception:
                pass
        # Plaintext is a test/local-only plugin and must never be enabled by default.
        if config.enable_plaintext_crypto:
            self._plugins[PlaintextPlugin.scheme] = PlaintextPlugin()

    def get(self, scheme: str):
        return self._plugins.get(scheme)

    def schemes(self) -> list[str]:
        return sorted(self._plugins)


registry = PluginRegistry()
