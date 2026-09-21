from __future__ import annotations

from fastapi import APIRouter
from server.config import config

router = APIRouter(prefix="/api", tags=["Cryptography & Key Management"])
bp = router  # Backward compatibility alias


@router.get("/v1/crypto/public-keys")
@router.get("/crypto/public-keys")
async def get_public_keys():
    """Returns active public keys and algorithms supported by the server for agent encryption."""
    keys = config.load_hpke_public_keys()
    return {
        "ok": True,
        "count": len(keys),
        "primary_key_id": config.hpke_key_id,
        "keys": keys,
    }
