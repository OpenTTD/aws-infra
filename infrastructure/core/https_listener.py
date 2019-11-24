from aws_cdk.core import (
    Construct,
    Duration,
    Stack,
)
from aws_cdk.aws_certificatemanager import (
    DnsValidatedCertificate,
    ValidationMethod,
)
from aws_cdk.aws_elasticloadbalancingv2 import (
    ApplicationListener,
    ApplicationProtocol,
    HealthCheck,
)
from aws_cdk.aws_route53 import HostedZone

from infrastructure.core.core import CoreStack


class HTTPSListenerStack(Stack):
    """Stack that handles the HTTPS Listener on the ALB."""

    def __init__(self, scope: Construct, id: str, core: CoreStack, hosted_zone_name: str, domain_name: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self._hosted_zone = HostedZone.from_lookup(self, "Zone",
            domain_name=hosted_zone_name,
        )
        self._domain_name = domain_name

        self._https_listener = ApplicationListener(self, "HTTPSListener",
            load_balancer=core.alb,
            port=443,
            protocol=ApplicationProtocol.HTTPS,
        )

        self._priority = 1

    def _add_certificate(self, fqdn: str) -> None:
        certificate = DnsValidatedCertificate(self, fqdn,
            hosted_zone=self._hosted_zone,
            domain_name=fqdn,
            validation_domains={
                fqdn: self._domain_name,
            },
            validation_method=ValidationMethod.DNS,
        )

        self._https_listener.add_certificate_arns(fqdn,
            arns=[certificate.certificate_arn],
        )

    def _get_health_check(self):
        return HealthCheck(
            healthy_http_codes="200",
            healthy_threshold_count=5,
            interval=Duration.seconds(30),
            path="/healthz",
            timeout=Duration.seconds(5),
            unhealthy_threshold_count=2,
        )

    def add_targets(self, subdomain_name: str, port: int, service):
        fqdn = f"{subdomain_name}.{self._domain_name}"

        self._add_certificate(fqdn)

        self._https_listener.add_targets(fqdn,
            health_check=self._get_health_check(),
            port=port,
            protocol=ApplicationProtocol.HTTP,
            targets=[service],
            host_header=fqdn,
            priority=self._priority,
        )
        self._priority += 1

    def add_default_target(self, port: int, service):
        self._add_certificate(self._domain_name)

        self._https_listener.add_targets(self._domain_name,
            health_check=self._get_health_check(),
            port=port,
            protocol=ApplicationProtocol.HTTP,
            targets=[service],
        )
