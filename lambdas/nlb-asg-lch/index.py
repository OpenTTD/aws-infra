import boto3
import json
import os
import time
import urllib3

client_autoscaling = boto3.client("autoscaling")
client_ec2 = boto3.client("ec2")
client_route53 = boto3.client("route53")


def lambda_handler(event, context):
    domain_name = os.environ["DOMAIN_NAME"]
    hosted_zone_id = os.environ["HOSTED_ZONE_ID"]
    private_domain_name = os.environ["PRIVATE_DOMAIN_NAME"]
    private_hosted_zone_id = os.environ["PRIVATE_HOSTED_ZONE_ID"]

    lifecycle_event = json.loads(event["Records"][0]["Sns"]["Message"])
    instance_id = lifecycle_event.get("EC2InstanceId")
    if not instance_id:
        print("Got event without EC2InstanceId: " + json.dumps(event))
        return

    print(f"Domain-name: {domain_name}")
    print(f"Hosted-zone-id: {hosted_zone_id}")
    print(f"Private-domain-name: {private_domain_name}")
    print(f"Private-hosted-zone-id: {private_hosted_zone_id}")
    print(f"Instance-id: {instance_id}")
    print(f"Lifecycle-transition: {lifecycle_event['LifecycleTransition']}")

    if lifecycle_event["LifecycleTransition"] == "autoscaling:EC2_INSTANCE_TERMINATING":
        print("Instance is being terminated; updating Route53 ..")
        update_route53(
            lifecycle_event["AutoScalingGroupName"],
            domain_name,
            hosted_zone_id,
            private_domain_name,
            private_hosted_zone_id,
            ignore_instance_id=instance_id,
        )

        finish(lifecycle_event)
        return

    if lifecycle_event["LifecycleTransition"] == "autoscaling:EC2_INSTANCE_LAUNCHING":
        instances = client_ec2.describe_instances(InstanceIds=[instance_id])
        internal_ip = instances["Reservations"][0]["Instances"][0].get("PrivateIpAddress")
        if not internal_ip:
            # This is most likely a retry when we crashed or something; not
            # really a state we can recover from, so just forget about it.
            print("No private ip found; most likely a retry. Aborting.")
            return

        print(f"Waiting for webserver on internal-ip {internal_ip} to respond ..")
        while not passes_health_check(internal_ip):
            time.sleep(10)

        finish(lifecycle_event)

        print("Instance online and healthy; updating Route53 ..")
        update_route53(
            lifecycle_event["AutoScalingGroupName"],
            domain_name,
            hosted_zone_id,
            private_domain_name,
            private_hosted_zone_id,
            additional_instance_id=instance_id,
        )
        return

    print(f"Unknown LifecycleTransition: {lifecycle_event['LifecycleTransition']}")
    finish(lifecycle_event)


def finish(lifecycle_event):
    client_autoscaling.complete_lifecycle_action(
        LifecycleActionResult="CONTINUE",
        **pick(lifecycle_event, "LifecycleHookName", "LifecycleActionToken", "AutoScalingGroupName"),
    )


def passes_health_check(ip):
    http = urllib3.PoolManager()
    try:
        response = http.request(
            "GET", f"http://{ip}/healthz", timeout=urllib3.Timeout(connect=1, read=1), retries=False
        )
        return response.status == 200
    except urllib3.exceptions.NewConnectionError:
        return False
    except urllib3.exceptions.ConnectTimeoutError:
        return False


def pick(dct, *keys):
    """Pick a subset of a dict."""
    return {k: v for k, v in dct.items() if k in keys}


def update_route53(
    auto_scaling_group_name,
    domain_name,
    hosted_zone_id,
    private_domain_name,
    private_hosted_zone_id,
    ignore_instance_id=None,
    additional_instance_id=None,
):
    ipv4s, ipv6s, private_ipv4s = get_ips_from_asg(
        auto_scaling_group_name, ignore_instance_id=ignore_instance_id, additional_instance_id=additional_instance_id
    )

    if not ipv4s or not ipv6s or not private_ipv4s:
        print("There were no active instances for this AutoscalingGroup; not updating route53!")
        return

    client_route53.change_resource_record_sets(
        HostedZoneId=hosted_zone_id,
        ChangeBatch={
            "Changes": [
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": domain_name,
                        "Type": "A",
                        "TTL": 60,
                        "ResourceRecords": [{"Value": ipv4} for ipv4 in ipv4s],
                    },
                },
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": domain_name,
                        "Type": "AAAA",
                        "TTL": 60,
                        "ResourceRecords": [{"Value": ipv6} for ipv6 in ipv6s],
                    },
                },
            ]
        },
    )

    client_route53.change_resource_record_sets(
        HostedZoneId=private_hosted_zone_id,
        ChangeBatch={
            "Changes": [
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": private_domain_name,
                        "Type": "A",
                        "TTL": 60,
                        "ResourceRecords": [{"Value": ipv4} for ipv4 in private_ipv4s],
                    },
                },
            ]
        },
    )


def get_ips_from_asg(auto_scaling_group_name, ignore_instance_id=None, additional_instance_id=None):
    asg = client_autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[auto_scaling_group_name])
    instance_ids = [
        instance["InstanceId"]
        for instance in asg["AutoScalingGroups"][0]["Instances"]
        if instance["LifecycleState"] == "InService"
    ]

    # Depending if an instance is terminating or launching, we might need to
    # manipulate this list a bit. A launching instance is not "InService" yet,
    # and a terminating instance should not be "InService" anymore. Just some
    # fail-safes.
    if ignore_instance_id:
        if ignore_instance_id in instance_ids:
            instance_ids.remove(ignore_instance_id)
    if additional_instance_id:
        if additional_instance_id not in instance_ids:
            instance_ids.append(additional_instance_id)

    instances = client_ec2.describe_instances(InstanceIds=instance_ids)

    ipv4s = set()
    ipv6s = set()
    private_ipv4s = set()
    for reserveration in instances["Reservations"]:
        for instance in reserveration["Instances"]:
            ipv4s.add(instance["PublicIpAddress"])
            ipv6s.add(instance["NetworkInterfaces"][0]["Ipv6Addresses"][0]["Ipv6Address"])
            private_ipv4s.add(instance["PrivateIpAddress"])

    return ipv4s, ipv6s, private_ipv4s
