import boto3
import json
import os
import time
import urllib3

client_autoscaling = boto3.client("autoscaling")
client_ec2 = boto3.client("ec2")


def lambda_handler(event, context):
    print(json.dumps(event))

    subdomain = os.environ["SUBDOMAIN"]
    hosted_zone_id = os.environ["HOSTED_ZONE_ID"]

    lifecycle_event = json.loads(event["Records"][0]["Sns"]["Message"])
    instance_id = lifecycle_event.get("EC2InstanceId")
    if not instance_id:
        print("Got event without EC2InstanceId: " + json.dumps(event))
        return

    print(f"Subdomain: {subdomain}")
    print(f"Hosted-zone-id: {hosted_zone_id}")
    print(f"Instance-id: {instance_id}")
    print(f"Lifecycle-transition: {lifecycle_event['LifecycleTransition']}")

    if lifecycle_event["LifecycleTransition"] == "autoscaling:EC2_INSTANCE_TERMINATING":
        print("Should remove DNS entry here")
        # TODO -- Remove DNS entry

        finish(lifecycle_event)
        return

    if lifecycle_event["LifecycleTransition"] == "autoscaling:EC2_INSTANCE_LAUNCHING":
        instances = client_ec2.describe_instances(InstanceIds=[instance_id])
        if "PrivateIpAddress" not in instances["Reservations"][0]["Instances"][0]:
            # This is most likely a retry when we crashed or something; not
            # really a state we can recover from, so just forget about it.
            print("No private ip found; most likely a retry. Aborting.")
            return
        internal_ip = instances["Reservations"][0]["Instances"][0]["PrivateIpAddress"]

        print(f"Waiting for webserver on internal-ip {internal_ip} to respond ..")
        while not passes_health_check(internal_ip):
            time.sleep(10)

        print("Should add DNS entry here")
        # TODO -- Add DNS entry
        finish(lifecycle_event)
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
        response = http.request("GET", f"http://{ip}/healthz", timeout=urllib3.Timeout(connect=1, read=1), retries=False)
        return response.status == 200
    except urllib3.exceptions.NewConnectionError:
        return False
    except urllib3.exceptions.ConnectTimeoutError:
        return False


def pick(dct, *keys):
    """Pick a subset of a dict."""
    return {k: v for k, v in dct.items() if k in keys}
