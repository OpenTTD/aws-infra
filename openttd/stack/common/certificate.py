from aws_cdk.core import (
    Construct,
    Stack,
    Tag,
)
from aws_cdk.aws_certificatemanager import (
    DnsValidatedCertificate,
    ICertificate,
    ValidationMethod,
)
from aws_cdk.aws_route53 import HostedZone
from typing import Optional

from openttd.stack.common import dns

g_certificate = None  # type: Optional[CertificateStack]


class CertificateResult:
    def __init__(self, certificate_arn, fqdn):
        self.certificate_arn = certificate_arn
        self.fqdn = fqdn


class CertificateStack(Stack):
    """
    Stack that creates all the Certificates.

    As provisioning Certificates is both slow, but also count towards a global
    yearly counter, we want to avoid recreating Certificates as much as
    possible. By creating them in a single stack, we can cycle the other
    stacks without having to worry about Certificates.
    """

    def __init__(self,
                 scope: Construct,
                 id: str,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        global g_certificate

        self._last_certificate = None  # type: Optional[DnsValidatedCertificate]

        Tag.add(self, "Stack", "Common-Certificate")

        if g_certificate is not None:
            raise Exception("Only a single CertificateStack instance can exist")
        g_certificate = self

    def add_certificate(self, subdomain_name: str) -> CertificateResult:
        fqdn = dns.subdomain_to_fqdn(subdomain_name)

        certificate = DnsValidatedCertificate(self, f"{fqdn}-Certificate",
            hosted_zone=dns.get_hosted_zone(),
            domain_name=fqdn,
            validation_domains={
                fqdn: dns.get_domain_name(),
            },
            validation_method=ValidationMethod.DNS,
        )

        # With more than 4 certificates, we hit the rate limiter, as
        # CustomResources are all triggered at the same time. To prevent this,
        # we make all the CustomResource nodes inside DnsValidatedCertificate
        # depend on each other. This means that one has to finish before the
        # next is started, preventing this issue.
        if self._last_certificate is not None:
            certificate.node.children[-1].node.add_dependency(self._last_certificate.node.children[-1])
        self._last_certificate = certificate

        return CertificateResult(certificate.certificate_arn, fqdn)


def add_certificate(subdomain_name: str) -> CertificateResult:
    if g_certificate is None:
        raise Exception("No CertificateStack instance exists")

    return g_certificate.add_certificate(subdomain_name)
