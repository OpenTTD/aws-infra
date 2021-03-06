from aws_cdk.core import (
    Construct,
    Duration,
    Stack,
    Tags,
)
from aws_cdk.aws_elasticloadbalancingv2 import (
    ApplicationListener,
    ApplicationProtocol,
    ApplicationTargetGroup,
    IApplicationLoadBalancer,
    IApplicationLoadBalancerTarget,
    HealthCheck,
)
from aws_cdk.aws_ec2 import Peer
from aws_cdk.aws_route53_targets import LoadBalancerTarget
from typing import Optional

from openttd.construct.dns import (
    ARecord,
    AaaaRecord,
)
from openttd.stack.common import (
    certificate,
    dns,
)

g_listener_https = None  # type: Optional[ListenerHttpsStack]


class ListenerHttpsStack(Stack):
    """
    Stack to the HTTPS Listener on the ALB.

    As there can be only a single HTTPS Listener, and many other stacks
    create containers that want to use it, they are created via this one
    single stack.
    """

    def __init__(self, scope: Construct, id: str, *, alb: IApplicationLoadBalancer, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        global g_listener_https

        Tags.of(self).add("Stack", "Common-Listener-Https")

        self._used_priorities = []
        self._subdomains_cert = {}

        self._alb = alb
        self._listener = ApplicationListener(
            self,
            "Listener-Https",
            load_balancer=alb,
            port=443,
            protocol=ApplicationProtocol.HTTPS,
        )
        # By default, only IPv4 is added to allowed connections
        self._listener.connections.allow_default_port_from(
            other=Peer.any_ipv6(),
            description="Allow from anyone on port 443",
        )
        # Make sure there is always a backend picking up, even if we don't know the host
        self._listener.add_fixed_response(
            "default",
            status_code="404",
            message_body="Page not found",
        )

        # Add a redirect; in case people go to HTTP, redirect them to HTTPS.
        self._http_listener = ApplicationListener(
            self,
            "Listener-Http",
            load_balancer=alb,
            port=80,
            protocol=ApplicationProtocol.HTTP,
        )
        self._http_listener.connections.allow_default_port_from(
            other=Peer.any_ipv6(),
            description="Allow from anyone on port 80",
        )
        self._http_listener.add_redirect_response(
            "Http-To-Https",
            status_code="HTTP_301",
            port="443",
            protocol="HTTPS",
        )

        if g_listener_https is not None:
            raise Exception("Only a single ListenerHTTPSStack instance can exist")
        g_listener_https = self

    def _get_health_check(self):
        return HealthCheck(
            healthy_http_codes="200",
            healthy_threshold_count=5,
            interval=Duration.seconds(30),
            path="/healthz",
            timeout=Duration.seconds(5),
            unhealthy_threshold_count=2,
        )

    def add_targets(
        self,
        subdomain_name: str,
        port: int,
        target: IApplicationLoadBalancerTarget,
        priority: int,
        *,
        path_pattern: Optional[str] = None,
        allow_via_http: Optional[bool] = False,
        no_dns: Optional[bool] = False,
        target_group: Optional[ApplicationTargetGroup] = None,
    ) -> ApplicationTargetGroup:
        fqdn = dns.subdomain_to_fqdn(subdomain_name)

        cert = self._subdomains_cert.get(fqdn)
        if not cert:
            cert = certificate.add_certificate(subdomain_name)

            self._listener.add_certificate_arns(
                fqdn,
                arns=[cert.certificate_arn],
            )

        # Prevent two services using the same priority
        if priority in self._used_priorities:
            raise Exception(f"Priority {priority} already used")
        self._used_priorities.append(priority)

        if path_pattern:
            id = f"{fqdn}-{path_pattern}"
        else:
            id = fqdn

        if target_group is not None:
            self._listener.add_target_groups(
                id,
                target_groups=[target_group],
                host_header=fqdn,
                path_pattern=path_pattern,
                priority=priority,
            )
        else:
            target_group = self._listener.add_targets(
                id,
                deregistration_delay=Duration.seconds(30),
                slow_start=Duration.seconds(30),
                health_check=self._get_health_check(),
                port=port,
                protocol=ApplicationProtocol.HTTP,
                targets=[target],
                host_header=fqdn,
                path_pattern=path_pattern,
                priority=priority,
            )

        if allow_via_http:
            self._http_listener.add_target_groups(
                f"{id}http",
                target_groups=[target_group],
                host_header=fqdn,
                path_pattern=path_pattern,
                priority=priority,
            )

        if fqdn not in self._subdomains_cert:
            if not no_dns:
                ARecord(
                    self,
                    f"{cert.fqdn}-ARecord",
                    fqdn=cert.fqdn,
                    target=LoadBalancerTarget(self._alb),
                )
                AaaaRecord(
                    self,
                    f"{cert.fqdn}-AaaaRecord",
                    fqdn=cert.fqdn,
                    target=LoadBalancerTarget(self._alb),
                )

            self._subdomains_cert[fqdn] = cert

        return target_group


def add_targets(
    subdomain_name: str,
    port: int,
    target: IApplicationLoadBalancerTarget,
    priority: int,
    *,
    path_pattern: Optional[str] = None,
    allow_via_http: Optional[bool] = False,
    no_dns: Optional[bool] = False,
    target_group: Optional[ApplicationTargetGroup] = None,
) -> ApplicationTargetGroup:
    if g_listener_https is None:
        raise Exception("No ListenerHTTPSStack instance exists")

    return g_listener_https.add_targets(
        subdomain_name,
        port,
        target,
        priority,
        path_pattern=path_pattern,
        allow_via_http=allow_via_http,
        no_dns=no_dns,
        target_group=target_group,
    )
