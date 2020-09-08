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
            desired_count = 1  # Currently this pod is stateful, and as such cannot be run more than once
            priority = 60
        else:
            desired_count = 1
            priority = 160

        sentry_dsn = parameter_store.add_secure_string(f"/MasterServerApi/{deployment.value}/SentryDSN").parameter

        self.container = ECSHTTPSContainer(self, self.application_name,
            subdomain_name=self.subdomain_name,
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="openttd/master-server",
            port=80,
            memory_limit_mib=128,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            command=[
                "--app", "web_api",
                "--bind", "0.0.0.0",
                "--db", "dynamodb",
                "--dynamodb-region", "eu-central-1",
            ],
            environment={
                "MASTER_SERVER_SENTRY_ENVIRONMENT": deployment.value.lower(),
            },
            secrets={
                "MASTER_SERVER_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
            },
        )

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
            resources=[
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/MSU-ip-port",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/MSU-ip-port/index/online_view",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/MSU-ip-port/index/time_last_seen_view",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/MSU-server",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/MSU-server/index/online_view",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/MSU-server/index/time_last_seen_view",
            ]
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
        else:
            desired_count = 1
            priority = 161
            master_port = 4978

        sentry_dsn = parameter_store.add_secure_string(f"/MasterServer/{deployment.value}/SentryDSN").parameter

        self.container = ECSHTTPSContainer(self, self.application_name,
            subdomain_name=self.subdomain_name,
            deployment=deployment,
            policy=policy,
            application_name=self.application_name,
            image_name="openttd/master-server",
            port=80,
            memory_limit_mib=128,
            desired_count=desired_count,
            cluster=cluster,
            priority=priority,
            command=[
                "--app", "master_server",
                "--bind", "0.0.0.0",
                "--msu-port", str(master_port),
                "--db", "dynamodb",
                "--dynamodb-region", self.region,
                "--proxy-protocol",
            ],
            environment={
                "MASTER_SERVER_SENTRY_ENVIRONMENT": deployment.value.lower(),
            },
            secrets={
                "MASTER_SERVER_SENTRY_DSN": Secret.from_ssm_parameter(sentry_dsn),
            },
        )

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
            resources=[
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/MSU-ip-port",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/MSU-ip-port/index/online_view",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/MSU-ip-port/index/time_last_seen_view",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/MSU-server",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/MSU-server/index/online_view",
                f"arn:aws:dynamodb:{self.region}:{self.account}:table/MSU-server/index/time_last_seen_view",
            ]
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
            image_name="openttd/master-server-web",
            port=80,
            memory_limit_mib=128,
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
