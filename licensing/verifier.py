import base64
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from .exceptions import InvalidSignatureException

PUBLIC_KEY = Path(__file__).resolve().parent / "public_key.pem"


def load_public_key():

    with open(PUBLIC_KEY, "rb") as f:
        return serialization.load_pem_public_key(
            f.read()
        )


def verify_signature(payload, signature):

    payload_bytes = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":")
    ).encode()

    signature = base64.b64decode(signature)

    public_key = load_public_key()

    try:

        public_key.verify(

            signature,

            payload_bytes,

            padding.PSS(

                mgf=padding.MGF1(hashes.SHA256()),

                salt_length=padding.PSS.MAX_LENGTH

            ),

            hashes.SHA256()

        )

        return True

    except InvalidSignature:
        raise InvalidSignatureException(
            "Invalid RSA Signature."
        )