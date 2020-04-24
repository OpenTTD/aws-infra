
#
# DONE - ASG with EC2 t3a.nano over two AZs
# DONE -EC2 with UserData, installs:
# DONE - - Traefik 2.2
# DONE - - Python script to generate config
#          Script can also be called via internal HTTP request to reload
# DONE - Lifecycle Hook on ASG to Lambda
# TODO - Lambda responds to scale up/down, updates DNS record with external IPv4 and IPv6
# TODO - CloudWatch event on ECS change to Lambda
# TODO - Lambda calls Python script on EC2 instances
#

#
# In the end we have:
#   content.openttd.org     CNAME       nlb.openttd.org
#   nlb.openttd.org         A           <IPv4 of EC2-1>
#   nlb.openttd.org         A           <IPv4 of EC2-2>
#   nlb.openttd.org         AAAA        <IPv6 of EC2-1>
#   nlb.openttd.org         AAAA        <IPv6 of EC2-2>
#
# On ASG scale, Lambda updates the above IPs.
# On ECS mutation, Lambda calls Python script on EC2-1 and EC2-2.
#   This results in a new traefik config, which is reloaded.
#

import os

from aws_cdk.core import (
    Construct,
    Duration,
    Stack,
    Tag,
)
from aws_cdk.aws_autoscaling import (
    AutoScalingGroup,
    DefaultResult,
    HealthCheck,
    LifecycleHook,
    LifecycleTransition,
)
from aws_cdk.aws_autoscaling_hooktargets import FunctionHook
from aws_cdk.aws_ec2 import (
    AmazonLinuxGeneration,
    InstanceType,
    IVpc,
    MachineImage,
    Peer,
    Port,
    SecurityGroup,
    SubnetSelection,
    SubnetType,
    UserData,
)
from aws_cdk.aws_ecs import (
    ICluster,
    IEc2Service,
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
from aws_cdk.aws_s3_assets import Asset

from openttd.stack.common import (
    dns,
    listener_https,
)

g_nlb = None  # type: Optional[NlbStack]


class NlbStack(Stack):
    subdomain_name = "nlb"

    def __init__(self,
                 scope: Construct,
                 id: str,
                 ecs: ICluster,
                 vpc: IVpc,
                 **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        global g_nlb

        Tag.add(self, "Stack", "Common-Nlb")

        # TODO -- You need to do some manual actions:
        # TODO --  1) enable auto-assign IPv6 address on public subnets
        # TODO --  2) add to the Outbound rules of "Live-Common-Nlb/ASG/InstanceSecurityGroup" the destination "::/0"

        user_data = UserData.for_linux(shebang="#!/bin/bash -ex")

        asset = Asset(self, "NLB", path="user_data/nlb/")
        user_data.add_commands(
            "echo 'Extracting user-data files'",
            "mkdir /nlb",
            "cd /nlb",
        )
        user_data.add_s3_download_command(
            bucket=asset.bucket,
            bucket_key=asset.s3_object_key,
            local_file="/nlb/files.zip",
        )
        user_data.add_commands(
            "unzip files.zip",
        )

        user_data.add_commands(
            "echo 'Setting up configuration'",
            f"echo '{self.region}' > /etc/.region",
            f"echo '{ecs.cluster.cluster_name}' > /etc/.cluster",
        )

        user_data.add_commands(
            "echo 'Installing nginx'",
            "amazon-linux-extras install epel",
            "yum install nginx -y",
            "cp /nlb/nginx.conf /etc/nginx/nginx.conf",
            "mkdir /etc/nginx/nlb.d",
        )

        user_data.add_commands(
            "echo 'Installing Python3'",
            "yum install python3 -y",
            "python3 -m venv /venv",
            "/venv/bin/pip install -r /nlb/requirements.txt",
        )

        user_data.add_commands(
            "echo 'Generating nginx configuration'",
            "cd /etc/nginx/nlb.d",
            "/venv/bin/python /nlb/nginx.py",
            "systemctl start nginx",
        )

        asg = AutoScalingGroup(self, "ASG",
            vpc=vpc,
            instance_type=InstanceType("t3a.nano"),
            machine_image=MachineImage.latest_amazon_linux(generation=AmazonLinuxGeneration.AMAZON_LINUX_2),
            min_capacity=2,
            vpc_subnets=SubnetSelection(subnet_type=SubnetType.PUBLIC, one_per_az=True),
            user_data=user_data,
            health_check=HealthCheck.elb(grace=Duration.seconds(0)),
        )
        asg.add_security_group(ecs.security_group)

        asg.role.add_managed_policy(ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"))
        asset.grant_read(asg.role)
        policy = ManagedPolicy(self, "Policy")
        policy_statement = PolicyStatement(
            actions=[
                "ec2:DescribeInstances",
                "ecs:DescribeContainerInstances",
                "ecs:DescribeTasks",
                "ecs:ListContainerInstances",
                "ecs:ListServices",
                "ecs:ListTagsForResource",
                "ecs:ListTasks",
            ],
            resources=["*"],
        )
        policy.add_statements(policy_statement)
        asg.role.add_managed_policy(policy)

        # We could also make an additional security-group and add that to
        # the ASG, but it keeps adding up. This makes it a tiny bit
        # easier to get an overview what traffic is allowed from the
        # console on AWS.
        assert(isinstance(asg.node.children[0], SecurityGroup))
        self.security_group = asg.node.children[0]

        listener_https.add_targets(
            subdomain_name=self.subdomain_name,
            port=80,
            target=asg,
            priority=1,
        )

        # Create a Security Group so the lambdas can access the EC2.
        # This is needed to check if the EC2 instance is fully booted.
        lambda_security_group = SecurityGroup(self, "LambdaSG",
            vpc=vpc,
        )
        self.security_group.add_ingress_rule(
            peer=lambda_security_group,
            connection=Port.tcp(80),
            description="Lambda to target",
        )

        self.create_lambda(
            lifecycle_transition=LifecycleTransition.INSTANCE_LAUNCHING,
            timeout=Duration.seconds(180),
            vpc=vpc,
            security_group=lambda_security_group,
            auto_scaling_group=asg
        )
        self.create_lambda(
            lifecycle_transition=LifecycleTransition.INSTANCE_TERMINATING,
            timeout=Duration.seconds(30),
            vpc=vpc,
            security_group=lambda_security_group,
            auto_scaling_group=asg,
        )

        if g_nlb is not None:
            raise Exception("Only a single NlbStack instance can exist")
        g_nlb = self

    def create_lambda(self, lifecycle_transition: LifecycleTransition, timeout: Duration, vpc: IVpc, security_group: SecurityGroup, auto_scaling_group: AutoScalingGroup):
        if lifecycle_transition == LifecycleTransition.INSTANCE_LAUNCHING:
            name = "Launch"
        else:
            name = "Terminate"

        lambda_func = Function(self, f"Lambda{name}",
            code=Code.from_asset("./lambdas/nlb-asg-lch"),
            handler='index.lambda_handler',
            runtime=Runtime.PYTHON_3_8,
            timeout=Duration.seconds(timeout.to_seconds() + 20),  # Slightly more than the Lifecycle Hook timeout
            environment={
                "SUBDOMAIN": f"{self.subdomain_name}.aws",
                "HOSTED_ZONE_ID": dns.get_hosted_zone().hosted_zone_id,
            },
            vpc=vpc,
            security_groups=[security_group],
        )

        auto_scaling_group.add_lifecycle_hook(f"LH{name}",
            lifecycle_transition=LifecycleTransition.INSTANCE_LAUNCHING,
            notification_target=FunctionHook(lambda_func),
            default_result=DefaultResult.ABANDON if lifecycle_transition == LifecycleTransition.INSTANCE_LAUNCHING else DefaultResult.CONTINUE,
            heartbeat_timeout=timeout,
        )

        lambda_func.add_to_role_policy(PolicyStatement(
            actions=[
                "ec2:DescribeInstances",
            ],
            resources=["*"],
        ))
        lambda_func.add_to_role_policy(PolicyStatement(
            actions=[
                "autoscaling:CompleteLifecycleAction",
            ],
            resources=[auto_scaling_group.auto_scaling_group_arn],
        ))

    def add_nlb(self, service: IEc2Service, port: Port, subdomain_name: str, description: str) -> None:
        port_dict = port.to_rule_json()
        Tag.add(service, "NLB-protocol", port_dict["ipProtocol"])
        Tag.add(service, "NLB-port", str(port_dict["fromPort"]))
        Tag.add(service, "NLB-subdomain", subdomain_name)

        self.security_group.add_ingress_rule(
            peer=Peer.any_ipv6(),
            connection=port,
            description=f"{description} (IPv6)"
        )
        self.security_group.add_ingress_rule(
            peer=Peer.any_ipv4(),
            connection=port,
            description=f"{description} (IPv4)"
        )


def add_nlb(service: IEc2Service, port: Port, subdomain_name: str, description: str) -> None:
    if g_nlb is None:
        raise Exception("No NlbStack instance exists")

    return g_nlb.add_nlb(service, port, subdomain_name, description)
