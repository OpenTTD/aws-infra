import boto3
import json
import os
import time

from botocore.exceptions import ClientError

client_autoscaling = boto3.client("autoscaling")
client_ssm = boto3.client("ssm")


def lambda_handler(event, context):
    print(json.dumps(event))

    auto_scaling_group_name = os.environ["AUTO_SCALING_GROUP_NAME"]

    asg = client_autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[auto_scaling_group_name])
    instance_ids = [
        instance["InstanceId"]
        for instance in asg["AutoScalingGroups"][0]["Instances"]
        if instance["LifecycleState"] == "InService"
    ]

    print(f"Starting nlb-reload on {len(instance_ids)} instances ..")

    response = client_ssm.send_command(
        InstanceIds=instance_ids,
        DocumentName="AWS-RunShellScript",
        DocumentVersion="1",
        Parameters={
            "commands": [
                "cd /etc/nginx/nlb.d",
                "/venv/bin/python /nlb/nginx.py",
                "systemctl reload nginx",
            ]
        },
    )
    command_id = response["Command"]["CommandId"]

    for instance_id in instance_ids:
        print(f"Waiting for {instance_id} to finish ..")

        while True:
            time.sleep(1)

            try:
                response = client_ssm.get_command_invocation(
                    CommandId=command_id,
                    InstanceId=instance_id,
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "InvocationDoesNotExist":
                    continue
                raise

            if response["Status"] == "InProgress":
                continue

            print(f"{instance_id} finished with status {response['Status']}")
            break
