from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import platform
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
    CERT_DIR = Path(os.environ["LOCALAPPDATA"]) / "MetaVerseSquadFinder" / "trusted_https"
else:
    CERT_DIR = INSTANCE_DIR / "trusted_https"
CA_KEY_PATH = CERT_DIR / "squadfinder_local_ca_key.pem"
CA_CERT_PATH = CERT_DIR / "squadfinder_local_ca.crt"
CA_CERT_DER_PATH = CERT_DIR / "squadfinder_local_ca.cer"
SERVER_KEY_PATH = CERT_DIR / "squadfinder_server_key.pem"
SERVER_CERT_PATH = CERT_DIR / "squadfinder_server.crt"
INFO_PATH = CERT_DIR / "certificate_info.json"
URL_PATH = CERT_DIR / "secure_url.txt"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def write_private(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def discover_hostnames() -> list[str]:
    values = {"localhost"}
    for candidate in (socket.gethostname(), socket.getfqdn()):
        candidate = (candidate or "").strip().lower().rstrip(".")
        if candidate and candidate != "localhost":
            values.add(candidate)
    return sorted(values)


def discover_ips() -> list[ipaddress._BaseAddress]:
    values: set[ipaddress._BaseAddress] = {
        ipaddress.ip_address("127.0.0.1"),
        ipaddress.ip_address("::1"),
    }

    def consider(raw: str) -> None:
        try:
            addr = ipaddress.ip_address(raw.split("%", 1)[0])
        except ValueError:
            return
        if addr.is_unspecified or addr.is_multicast:
            return
        if isinstance(addr, ipaddress.IPv4Address) and addr.is_link_local:
            return
        values.add(addr)

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            consider(info[4][0])
    except OSError:
        pass

    # This asks Windows which local interface would be used. No payload is sent.
    for destination in (("8.8.8.8", 80), ("1.1.1.1", 80)):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(destination)
            consider(sock.getsockname()[0])
        except OSError:
            pass
        finally:
            sock.close()

    return sorted(values, key=lambda value: (value.version, int(value)))


def load_certificate(path: Path) -> x509.Certificate | None:
    if not path.exists():
        return None
    try:
        return x509.load_pem_x509_certificate(path.read_bytes())
    except (ValueError, OSError):
        return None


def cert_expiring(cert: x509.Certificate | None, within_days: int = 30) -> bool:
    if cert is None:
        return True
    expiry = getattr(cert, "not_valid_after_utc", None)
    if expiry is None:
        expiry = cert.not_valid_after.replace(tzinfo=timezone.utc)
    return expiry <= now_utc() + timedelta(days=within_days)


def cert_sans(cert: x509.Certificate | None) -> tuple[set[str], set[str]]:
    if cert is None:
        return set(), set()
    try:
        extension = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return set(), set()
    dns = {name.lower() for name in extension.get_values_for_type(x509.DNSName)}
    ips = {str(value) for value in extension.get_values_for_type(x509.IPAddress)}
    return dns, ips


def certificate_signed_by(cert: x509.Certificate | None, issuer: x509.Certificate) -> bool:
    if cert is None or cert.issuer != issuer.subject:
        return False
    try:
        issuer.public_key().verify(
            cert.signature,
            cert.tbs_certificate_bytes,
            padding.PKCS1v15(),
            cert.signature_hash_algorithm,
        )
        return True
    except Exception:
        return False


def create_ca() -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MetaVerse SquadFinder"),
        x509.NameAttribute(NameOID.COMMON_NAME, "MetaVerse SquadFinder Local CA"),
    ])
    current = now_utc()
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(current - timedelta(days=1))
        .not_valid_after(current + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    write_private(
        CA_KEY_PATH,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    CA_CERT_PATH.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    CA_CERT_DER_PATH.write_bytes(cert.public_bytes(serialization.Encoding.DER))
    return key, cert


def load_or_create_ca() -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    cert = load_certificate(CA_CERT_PATH)
    if CA_KEY_PATH.exists() and cert and not cert_expiring(cert, 365):
        try:
            key = serialization.load_pem_private_key(CA_KEY_PATH.read_bytes(), password=None)
            if isinstance(key, rsa.RSAPrivateKey):
                return key, cert
        except (ValueError, TypeError, OSError):
            pass
    return create_ca()


def create_server_certificate(
    ca_key: rsa.RSAPrivateKey,
    ca_cert: x509.Certificate,
    hostnames: list[str],
    ips: list[ipaddress._BaseAddress],
) -> x509.Certificate:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    current = now_utc()
    san_values: list[x509.GeneralName] = [x509.DNSName(name) for name in hostnames]
    san_values.extend(x509.IPAddress(addr) for addr in ips)
    cert = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MetaVerse SquadFinder"),
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ])
        )
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(current - timedelta(days=1))
        .not_valid_after(current + timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(san_values), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    write_private(
        SERVER_KEY_PATH,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    SERVER_CERT_PATH.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert


def ensure_certificates() -> dict[str, object]:
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    ca_key, ca_cert = load_or_create_ca()
    hostnames = discover_hostnames()
    ips = discover_ips()
    expected_dns = {value.lower() for value in hostnames}
    expected_ips = {str(value) for value in ips}

    server_cert = load_certificate(SERVER_CERT_PATH)
    existing_dns, existing_ips = cert_sans(server_cert)
    if (
        not SERVER_KEY_PATH.exists()
        or cert_expiring(server_cert)
        or not expected_dns.issubset(existing_dns)
        or not expected_ips.issubset(existing_ips)
        or not certificate_signed_by(server_cert, ca_cert)
    ):
        server_cert = create_server_certificate(ca_key, ca_cert, hostnames, ips)

    fingerprint = ca_cert.fingerprint(hashes.SHA256()).hex().upper()
    fingerprint_colon = ":".join(fingerprint[index : index + 2] for index in range(0, len(fingerprint), 2))
    lan_ips = [str(value) for value in ips if isinstance(value, ipaddress.IPv4Address) and not value.is_loopback]
    info: dict[str, object] = {
        "generated_at": now_utc().isoformat(),
        "computer": platform.node(),
        "hostnames": hostnames,
        "ip_addresses": [str(value) for value in ips],
        "lan_urls": [f"https://{value}:5443" for value in lan_ips],
        "local_url": "https://localhost:5443",
        "ca_sha256": fingerprint_colon,
        "ca_certificate": str(CA_CERT_DER_PATH),
        "server_certificate": str(SERVER_CERT_PATH),
        "server_key": str(SERVER_KEY_PATH),
    }
    INFO_PATH.write_text(json.dumps(info, indent=2), encoding="utf-8")
    URL_PATH.write_text("https://localhost:5443\n", encoding="utf-8")
    return info


def install_windows_trust() -> bool:
    if os.name != "nt":
        print("Trusted-root installation is only automatic on Windows.")
        return False
    certutil = os.environ.get("SystemRoot", r"C:\Windows") + r"\System32\certutil.exe"
    command = [certutil, "-user", "-f", "-addstore", "Root", str(CA_CERT_DER_PATH)]
    result = subprocess.run(command, capture_output=True, text=True)
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        print(output.strip())
        return False
    print("The SquadFinder local certificate authority is trusted for this Windows user.")
    return True


def uninstall_windows_trust() -> bool:
    cert = load_certificate(CA_CERT_PATH)
    if cert is None or os.name != "nt":
        return False
    thumbprint = cert.fingerprint(hashes.SHA1()).hex().upper()
    certutil = os.environ.get("SystemRoot", r"C:\Windows") + r"\System32\certutil.exe"
    result = subprocess.run(
        [certutil, "-user", "-delstore", "Root", thumbprint],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("SquadFinder local certificate trust was removed from this Windows user.")
        return True
    print(((result.stdout or "") + (result.stderr or "")).strip())
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare trusted local HTTPS for MetaVerse SquadFinder.")
    parser.add_argument("--install-trust", action="store_true", help="Trust the generated local CA for the current Windows user.")
    parser.add_argument("--uninstall-trust", action="store_true", help="Remove the generated local CA from the current Windows user trust store.")
    parser.add_argument("--print-url", action="store_true", help="Print the preferred local HTTPS URL only.")
    args = parser.parse_args()

    info = ensure_certificates()
    if args.uninstall_trust:
        return 0 if uninstall_windows_trust() else 1
    if args.install_trust and not install_windows_trust():
        print("Could not install local certificate trust automatically.")
        return 1
    if args.print_url:
        print(info["local_url"])
    else:
        print(f"Secure local URL: {info['local_url']}")
        for url in info["lan_urls"]:
            print(f"LAN URL: {url}")
        print(f"CA SHA-256: {info['ca_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
