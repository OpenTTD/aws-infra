from aws_cdk.core import (
    Construct,
    Stack,
    Tags,
)
from aws_cdk.aws_route53 import HostedZone
from typing import Optional

g_hosted_zone = None  # type: Optional[HostedZone]
g_hosted_zone_name = None  # type: Optional[str]
g_domain_name = None  # type: Optional[str]


class DnsStack(Stack):
    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 hosted_zone_name: str,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        global g_hosted_zone, g_hosted_zone_name

        Tags.of(self).add("Stack", "Common-Dns")

        if g_hosted_zone_name is not None:
            raise Exception("Only a single DNSStack instance can exist")

        g_hosted_zone_name = hosted_zone_name
        g_hosted_zone = HostedZone.from_lookup(self, "Zone",
            domain_name=hosted_zone_name,
        )


def get_hosted_zone_name() -> str:
    if g_hosted_zone_name is None:
        raise Exception("No DNSStack instance exists")

    return g_hosted_zone_name


def get_hosted_zone() -> HostedZone:
    if g_hosted_zone is None:
        raise Exception("No DNSStack instance exists")

    return g_hosted_zone


def set_domain_name(domain_name: str) -> None:
    global g_domain_name

    if g_hosted_zone_name is None:
        raise Exception("No DNSStack instance exists")

    if not domain_name.endswith(g_hosted_zone_name):
        raise Exception(f"Domain {domain_name} not within {g_hosted_zone_name}")

    g_domain_name = domain_name


def subdomain_to_fqdn(subdomain_name: str) -> str:
    if g_domain_name is None:
        raise Exception("No domain name was ever set")

    if subdomain_name == "@":
        return g_domain_name

    return f"{subdomain_name}.{g_domain_name}"


def get_domain_name() -> str:
    if g_domain_name is None:
        raise Exception("No domain name was ever set")

    return g_domain_name
