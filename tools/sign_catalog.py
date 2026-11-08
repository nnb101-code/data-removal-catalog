#!/usr/bin/env python3
"""
Signs catalog.json with ECDSA P-256 / SHA-256 and writes catalog.json.sig (base64 DER signature).
The private key (base64 PKCS#8 DER) comes from the CATALOG_SIGNING_KEY environment variable —
a GitHub Actions secret, never stored in the repository. The app holds only the public key.

Usage: CATALOG_SIGNING_KEY=... python3 tools/sign_catalog.py catalog.json
"""
import base64
import os
import sys

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


def main():
    path = sys.argv[1]
    raw_key = os.environ.get("CATALOG_SIGNING_KEY", "").strip()
    if not raw_key:
        print("ERROR: CATALOG_SIGNING_KEY is not set (add it under Settings → Secrets → Actions)", file=sys.stderr)
        sys.exit(1)
    key = serialization.load_der_private_key(base64.b64decode(raw_key), password=None)
    data = open(path, "rb").read()
    signature = key.sign(data, ec.ECDSA(hashes.SHA256()))
    # Verify with the public half before publishing, so a broken key never ships a bad signature.
    key.public_key().verify(signature, data, ec.ECDSA(hashes.SHA256()))
    with open(path + ".sig", "w") as f:
        f.write(base64.b64encode(signature).decode() + "\n")
    public = base64.b64encode(key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
    print(f"signed {path} ({len(data)} bytes); public key {public}")


if __name__ == "__main__":
    main()
