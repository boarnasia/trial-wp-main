import base64
import hashlib

from wp_main.trust import pem_sha1


def test_pem_sha1():
    der = b"dummy-der-bytes" * 5
    body = base64.b64encode(der).decode()
    pem = "-----BEGIN CERTIFICATE-----\n" + "\n".join(body[i:i + 64] for i in range(0, len(body), 64)) + "\n-----END CERTIFICATE-----\n"
    assert pem_sha1(pem) == hashlib.sha1(der).hexdigest().upper()
