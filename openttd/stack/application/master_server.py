from aws_cdk.core import (
    Construct,
    Duration,
    Stack,
    StringConcat,
    Tags,
)
from aws_cdk.aws_cloudfront import (
    LambdaEdgeEventType,
    LambdaFunctionAssociation,
    PriceClass,
    ViewerProtocolPolicy,
)
from aws_cdk.aws_ecs import (
    ICluster,
    IEc2Service,
    Secret,
)
from aws_cdk.aws_ec2 import (
    IVpc,
    Port,
    SecurityGroup,
)
from aws_cdk.aws_iam import (
    ManagedPolicy,
    PolicyStatement,
)
from aws_cdk.aws_lambda import (
    Code,
    Function,
    Runtime,
)
from aws_cdk.aws_s3 import Bucket
from typing import (
    List,
    Optional,
)

from openttd.construct.ecs_https_container import ECSHTTPSContainer
from openttd.construct.policy import Policy
from openttd.construct.s3_cloud_front import (
    S3CloudFront,
    S3CloudFrontPolicy,
)
from openttd.enumeration import Deployment
from openttd.stack.common import (
    dns,
    lambda_edge,
    nlb_self as nlb,
    parameter_store,
)


class MasterServerApiStack(Stack):
    application_name = "MasterServerApi"
    subdomain_name = "api.master"

    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 deployment: Deployment,
                 policy: Policy,
                 cluster: ICluster,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

        policy.add_stack(self)

        if deployment == Deployment.PRODUCTION:
            desired_count = 2
            priority = 60
            dynamodb_prefix = "P-"
        else:
            desired_count = 1
            priority = 160
            dynamodb_prefix = "S-"

        sentry_dsn = parameter_store.add_secure_string(f"/MasterServerApi/{deployment.value}/SentryDSN").parameter

        self.container = ECSHTTPSContainer(self, self.application_name,
            subdomain_name=self.subdomain_name,
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="ghcr.io/openttd/master-server",
            port=80,
            memory_limit_mib=96,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            command=[
                "--app", "web_api",
                "--bind", "0.0.0.0",
                "--db", "dynamodb",
                "--dynamodb-region", "eu-central-1",
                "--dynamodb-prefix", dynamodb_prefix,
            ],
            environment={
                "MASTER_SERVER_SENTRY_ENVIRONMENT": deployment.value.lower(),
            },
            secrets={
                "MASTER_SERVER_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
            },
        )

        table_and_index = []
        for table in ("S-MSU-ip-port", "S-MSU-server", "P-MSU-ip-port", "P-MSU-server"):
            table_and_index.extend([
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/{table}",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/{table}/index/online_view",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/{table}/index/time_last_seen_view",
            ])

        self.container.task_role.add_to_policy(PolicyStatement(
            actions=[
                "dynamodb:CreateTable",
                "dynamodb:UpdateTimeToLive",
                "dynamodb:PutItem",
                "dynamodb:DescribeTable",
                "dynamodb:ListTables",
                "dynamodb:GetItem",
                "dynamodb:Query",
                "dynamodb:UpdateItem"
            ],
            resources=table_and_index,
        ))


class MasterServerStack(Stack):
    application_name = "MasterServer"
    subdomain_name = "server.master"
    nlb_subdomain_name = "master"

    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 deployment: Deployment,
                 policy: Policy,
                 cluster: ICluster,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

        policy.add_stack(self)

        if deployment == Deployment.PRODUCTION:
            desired_count = 2
            priority = 61
            master_port = 3978
            dynamodb_prefix = "P-"
        else:
            desired_count = 1
            priority = 161
            master_port = 4978
            dynamodb_prefix = "S-"

        sentry_dsn = parameter_store.add_secure_string(f"/MasterServer/{deployment.value}/SentryDSN").parameter

        self.container = ECSHTTPSContainer(self, self.application_name,
            subdomain_name=self.subdomain_name,
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="ghcr.io/openttd/master-server",
            port=80,
            memory_limit_mib=64,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            command=[
                "--app", "master_server",
                "--bind", "0.0.0.0",
                "--msu-port", str(master_port),
                "--db", "dynamodb",
                "--dynamodb-region", self.region,
                "--dynamodb-prefix", dynamodb_prefix,
                "--proxy-protocol",
                "--socks-proxy", "socks5://nlb.openttd.internal:8080",
            ],
            environment={
                "MASTER_SERVER_SENTRY_ENVIRONMENT": deployment.value.lower(),
            },
            secrets={
                "MASTER_SERVER_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
            },
        )

        table_and_index = []
        for table in ("S-MSU-ip-port", "S-MSU-server", "P-MSU-ip-port", "P-MSU-server"):
            table_and_index.extend([
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/{table}",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/{table}/index/online_view",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/{table}/index/time_last_seen_view",
            ])

        self.container.task_role.add_to_policy(PolicyStatement(
            actions=[
                "dynamodb:CreateTable",
                "dynamodb:UpdateTimeToLive",
                "dynamodb:PutItem",
                "dynamodb:DescribeTable",
                "dynamodb:ListTables",
                "dynamodb:GetItem",
                "dynamodb:Query",
                "dynamodb:UpdateItem"
            ],
            resources=table_and_index,
        ))

        self.container.add_udp_port(master_port)
        nlb.add_nlb(self, self.container.service, Port.udp(master_port), self.nlb_subdomain_name, "Master Server")


class MasterServerWebStack(Stack):
    application_name = "MasterServerWeb"
    subdomain_name = "servers"

    def __init__(self,
                 scope: Construct,
                 id: str,
                 *,
                 deployment: Deployment,
                 policy: Policy,
                 cluster: ICluster,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("Application", self.application_name)
        Tags.of(self).add("Deployment", deployment.value)

        policy.add_stack(self)

        if deployment == Deployment.PRODUCTION:
            desired_count = 2
            priority = 62
        else:
            desired_count = 1
            priority = 162

        api_fqdn = dns.subdomain_to_fqdn("api.master")
        api_url = f"https://{api_fqdn}"

        sentry_dsn = parameter_store.add_secure_string(f"/MasterServerWeb/{deployment.value}/SentryDSN").parameter

        ECSHTTPSContainer(self, self.application_name,
            subdomain_name=self.subdomain_name,
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="ghcr.io/openttd/master-server-web",
            port=80,
            memory_limit_mib=96,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            command=[
                "--api-url", api_url,
                "run",
                "-p", "80",
                "-h", "0.0.0.0",
            ],
            environment={
                "WEBCLIENT_SENTRY_ENVIRONMENT": deployment.value.lower(),
            },
            secrets={
                "WEBCLIENT_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
            },
        )
