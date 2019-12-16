from aws_cdk.core import (
    Construct,
    Duration,
    Stack,
    Tag,
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
from aws_cdk.aws_route53 import (
    ARecord,
    HostedZone,
    RecordTarget,
)
from aws_cdk.aws_route53_targets import LoadBalancerTarget

from infrastructure.core.core import CoreStack


class ListenerHTTPSStack(Stack):
    """Stack that handles the HTTPS Listener on the ALB."""

    def __init__(self, scope: Construct, id: str, core: CoreStack, hosted_zone_name: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tag.add(self, "Stack", "Listener-HTTPS")

        self._hosted_zone_name = hosted_zone_name
        self._hosted_zone = HostedZone.from_lookup(self, "Zone",
            domain_name=hosted_zone_name,
        )

        self._alb = core.alb
        self._listener = ApplicationListener(self, "Listener-HTTPS",
            load_balancer=core.alb,
            port=443,
            protocol=ApplicationProtocol.HTTPS,
        )

        self._priority = 1

    def set_current_domain_name(self, domain_name: str):
        if not domain_name.endswith(self._hosted_zone_name):
            raise Exception("Domain name should end with the name of the hosted zone!")
        self._domain_name = domain_name

    def _add_certificate(self, fqdn: str) -> None:
        certificate = DnsValidatedCertificate(self, f"{fqdn}-Certificate",
            hosted_zone=self._hosted_zone,
            domain_name=fqdn,
            validation_domains={
                fqdn: self._domain_name,
            },
            validation_method=ValidationMethod.DNS,
        )

        self._listener.add_certificate_arns(fqdn,
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
        record_name = fqdn[0:-len(self._hosted_zone_name)-1]

        self._add_certificate(fqdn)

        ARecord(self, f"{fqdn}-arecord",
            target=RecordTarget.from_alias(LoadBalancerTarget(self._alb)),
            zone=self._hosted_zone,
            record_name=record_name,
        )

        self._listener.add_targets(fqdn,
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

        self._listener.add_targets(self._domain_name,
            health_check=self._get_health_check(),
            port=port,
            protocol=ApplicationProtocol.HTTP,
            targets=[service],
        )
