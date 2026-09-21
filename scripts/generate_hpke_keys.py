#!/usr/bin/env python3
"""
scripts/generate_hpke_keys.py
-----------------------------
Cryptographic keypair generation utility for InsiEDR Hybrid Public-Key Encryption (HPKE).
Generates RFC 9180 aligned X25519 keypairs for server telemetry decapsulation.

Usage:
    python scripts/generate_hpke_keys.py
    python scripts/generate_hpke_keys.py --key-id srv-x25519-2026-prod --out-dir ./keys
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path so shared module is importable
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from shared.crypto_utils import (
    generate_x25519_keypair,
    load_x25519_private_key,
    export_x25519_private_key,
    export_x25519_public_key,
    public_key_fingerprint,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate X25519 keypairs for InsiEDR Hybrid Public-Key Encryption (HPKE)"
    )
    parser.add_argument(
        "--key-id",
        type=str,
        default=None,
        help="Unique identifier for the generated key (defaults to srv-x25519-YYYYMMDD)",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="Optional directory to write private and public PEM files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    key_id = args.key_id or f"srv-x25519-{date_str}"

    raw_priv, raw_pub = generate_x25519_keypair()
    priv_obj = load_x25519_private_key(raw_priv)
    pub_obj = priv_obj.public_key()

    priv_b64 = export_x25519_private_key(priv_obj, as_pem=False)
    pub_b64 = export_x25519_public_key(pub_obj, as_pem=False)
    priv_pem = export_x25519_private_key(priv_obj, as_pem=True)
    pub_pem = export_x25519_public_key(pub_obj, as_pem=True)
    fingerprint = public_key_fingerprint(raw_pub)

    print("=" * 72)
    print("  InsiEDR HPKE (X25519) Cryptographic Keypair Generated")
    print("=" * 72)
    print(f"Key ID:             {key_id}")
    print(f"Algorithm:          DHKEM(X25519, HKDF-SHA256) + AES-256-GCM")
    print(f"Public Fingerprint: {fingerprint}")
    print("-" * 72)

    if args.out_dir:
        out_path = Path(args.out_dir).expanduser().resolve()
        out_path.mkdir(parents=True, exist_ok=True)
        priv_file = out_path / f"{key_id}.private.pem"
        pub_file = out_path / f"{key_id}.public.pem"

        priv_file.write_text(priv_pem, encoding="ascii")
        pub_file.write_text(pub_pem, encoding="ascii")
        try:
            os.chmod(priv_file, 0o600)
        except Exception:
            pass

        print(f"[+] Private key saved to: {priv_file}")
        print(f"[+] Public key saved to:  {pub_file}")
        print("-" * 72)

    print("\n[SERVER CONFIGURATION (.env or environment)]")
    print(f"INSIEDR_HPKE_KEY_ID={key_id}")
    print(f"INSIEDR_HPKE_PRIVATE_KEY={priv_b64}")
    if args.out_dir:
        print(f"# Or file-based: INSIEDR_HPKE_PRIVATE_KEY_PATH={priv_file}")

    print("\n[AGENT CONFIGURATION (.env or environment)]")
    print(f"INSIEDR_CRYPTO_SCHEME=hpke")
    print(f"INSIEDR_SERVER_KEY_ID={key_id}")
    print(f"INSIEDR_SERVER_PUBLIC_KEY={pub_b64}")

    print("\n" + "=" * 72)


if __name__ == "__main__":
    main()
