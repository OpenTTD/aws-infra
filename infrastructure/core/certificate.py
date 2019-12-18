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


class CertificateStack(Stack):
    """Stack that handles all the certificates."""

    def __init__(self, scope: Construct, id: str, hosted_zone_name: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tag.add(self, "Stack", "Certificate")

        self.hosted_zone_name = hosted_zone_name
        self.hosted_zone = HostedZone.from_lookup(self, "Zone",
            domain_name=hosted_zone_name,
        )

    def set_current_domain_name(self, domain_name: str):
        if not domain_name.endswith(self.hosted_zone_name):
            raise Exception("Domain name should end with the name of the hosted zone!")
        self.domain_name = domain_name

    def add_certificate(self, fqdn: str) -> ICertificate:
        certificate = DnsValidatedCertificate(self, f"{fqdn}-Certificate",
            hosted_zone=self.hosted_zone,
            domain_name=fqdn,
            validation_domains={
                fqdn: self.domain_name,
            },
            validation_method=ValidationMethod.DNS,
        )

        return certificate
