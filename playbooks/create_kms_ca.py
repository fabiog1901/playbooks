#!/usr/bin/env python3

import argparse
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from asn1crypto import core, keys, pem, x509


def build_ca_certificate(
    kms_client,
    key_id: str,
    organization: str,
    common_name: str,
    validity_days: int,
) -> bytes:
    key_response = kms_client.get_public_key(KeyId=key_id)

    if key_response["KeyUsage"] != "SIGN_VERIFY":
        raise ValueError(
            f"KMS key usage must be SIGN_VERIFY, "
            f"got {key_response['KeyUsage']}"
        )

    print(key_response['KeyId'])

    signing_algorithm = "RSASSA_PKCS1_V1_5_SHA_256"

    supported_algorithms = key_response.get("SigningAlgorithms", [])
    if signing_algorithm not in supported_algorithms:
        raise ValueError(
            f"{signing_algorithm} is not supported by this key. "
            f"Supported algorithms: {supported_algorithms}"
        )

    # AWS returns DER-encoded SubjectPublicKeyInfo.
    public_key_info = keys.PublicKeyInfo.load(key_response["PublicKey"])

    subject = x509.Name.build(
        {
            "organization_name": organization,
            "common_name": common_name,
        }
    )

    now = datetime.now(timezone.utc).replace(microsecond=0)
    not_before = now - timedelta(minutes=5)
    not_after = now + timedelta(days=validity_days)

    # RFC 5280 recommends a positive serial number no longer than 20 octets.
    serial_number = secrets.randbits(159)

    # SHA-1 here is the conventional Subject Key Identifier calculation.
    # It is an identifier, not the certificate signature algorithm.
    public_key_bytes = public_key_info["public_key"].contents
    subject_key_identifier = hashlib.sha1(public_key_bytes).digest()

    signature_algorithm = x509.SignedDigestAlgorithm(
        {"algorithm": "sha256_rsa"}
    )

    extensions = [
        x509.Extension(
            {
                "extn_id": "basic_constraints",
                "critical": True,
                "extn_value": x509.BasicConstraints(
                    {
                        "ca": True,
                        "path_len_constraint": 1,
                    }
                ),
            }
        ),
        x509.Extension(
            {
                "extn_id": "key_usage",
                "critical": True,
                "extn_value": x509.KeyUsage(
                    {
                        "digital_signature",
                        "key_cert_sign",
                        "crl_sign",
                    }
                ),
            }
        ),
        x509.Extension(
            {
                "extn_id": "key_identifier",
                "critical": False,
                "extn_value": subject_key_identifier,
            }
        ),
        x509.Extension(
            {
                "extn_id": "authority_key_identifier",
                "critical": False,
                "extn_value": x509.AuthorityKeyIdentifier(
                    {
                        "key_identifier": subject_key_identifier,
                    }
                ),
            }
        ),
    ]

    tbs_certificate = x509.TbsCertificate(
        {
            "version": "v3",
            "serial_number": serial_number,
            "signature": signature_algorithm,
            "issuer": subject,
            "validity": {
                "not_before": x509.Time(
                    {"utc_time": core.UTCTime(not_before)}
                ),
                "not_after": x509.Time(
                    {"utc_time": core.UTCTime(not_after)}
                ),
            },
            "subject": subject,
            "subject_public_key_info": public_key_info,
            "extensions": extensions,
        }
    )

    # X.509 signs the DER encoding of TBSCertificate.
    digest = hashlib.sha256(tbs_certificate.dump()).digest()

    sign_response = kms_client.sign(
        KeyId=key_id,
        Message=digest,
        MessageType="DIGEST",
        SigningAlgorithm=signing_algorithm,
    )

    certificate = x509.Certificate(
        {
            "tbs_certificate": tbs_certificate,
            "signature_algorithm": signature_algorithm,
            "signature_value": sign_response["Signature"],
        }
    )

    return pem.armor("CERTIFICATE", certificate.dump())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a self-signed CA certificate using AWS KMS"
    )
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--organization", required=True)
    parser.add_argument("--common-name", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--region")
    parser.add_argument("--profile")

    args = parser.parse_args()

    session = boto3.Session(
        profile_name=args.profile,
        region_name=args.region,
    )
    kms_client = session.client("kms")

    certificate_pem = build_ca_certificate(
        kms_client=kms_client,
        key_id=args.key_id,
        organization=args.organization,
        common_name=args.common_name,
        validity_days=args.days,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(certificate_pem)

    print(f"Created CA certificate: {output_path}")


if __name__ == "__main__":
    main()
