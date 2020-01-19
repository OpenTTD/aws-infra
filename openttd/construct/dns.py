from aws_cdk.core import Construct
import aws_cdk.aws_route53 as route53
from aws_cdk.aws_route53 import RecordTarget

from openttd.stack.common import dns


class ARecord(Construct):
    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 fqdn: str,
                 target) -> None:
        super().__init__(scope, id)

        hosted_zone_name = dns.get_hosted_zone_name()
        if not fqdn.endswith(hosted_zone_name):
            raise Exception(f"FQDN {fqdn} not within {hosted_zone_name}")
        record_name = fqdn[0:-len(hosted_zone_name) - 1]

        route53.ARecord(self, id,
            target=RecordTarget.from_alias(target),
            zone=dns.get_hosted_zone(),
            record_name=record_name,
        )

        # Create a second record under "aws" subdomain. This helps during
        # migration to CNAME the subdomain from the authority nameserver
        # to AWS (as in: www.openttd.org CNAME www.aws.openttd.org)
        route53.ARecord(self, f"{id}Alias",
            target=RecordTarget.from_alias(target),
            zone=dns.get_hosted_zone(),
            record_name=f"{record_name}.aws",
        )


class AaaaRecord(Construct):
    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 fqdn: str,
                 target) -> None:
        super().__init__(scope, id)

        hosted_zone_name = dns.get_hosted_zone_name()
        if not fqdn.endswith(hosted_zone_name):
            raise Exception(f"FQDN {fqdn} not within {hosted_zone_name}")
        record_name = fqdn[0:-len(hosted_zone_name) - 1]

        route53.AaaaRecord(self, id,
            target=RecordTarget.from_alias(target),
            zone=dns.get_hosted_zone(),
            record_name=record_name,
        )

        # Create a second record under "aws" subdomain. This helps during
        # migration to CNAME the subdomain from the authority nameserver
        # to AWS (as in: www.openttd.org CNAME www.aws.openttd.org)
        route53.AaaaRecord(self, f"{id}Alias",
            target=RecordTarget.from_alias(target),
            zone=dns.get_hosted_zone(),
            record_name=f"{record_name}.aws",
        )
