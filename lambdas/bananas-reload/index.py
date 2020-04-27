import boto3
import json
import os
import urllib3

client_ecs = boto3.client("ecs")
client_ec2 = boto3.client("ec2")


def lambda_handler(event, context):
    cluster = os.environ["CLUSTER"]
    service = os.environ["SERVICE"]

    secret = event["secret"]

    container_mapping = fetch_container_mapping(cluster)

    tasks = client_ecs.list_tasks(cluster=cluster, serviceName=service)
    tasks = client_ecs.describe_tasks(cluster=cluster, tasks=tasks["taskArns"])

    for task in tasks["tasks"]:
        if task["lastStatus"] != "RUNNING" or task["desiredStatus"] != "RUNNING":
            continue

        name = task["taskArn"].split(":")[-1]
        print(f"INFO: Reloading database of {name} ..")

        container_instance = task["containerInstanceArn"]
        for container in task["containers"]:
            for network_binding in container["networkBindings"]:
                if network_binding["containerPort"] == 80:
                    host_port = network_binding["hostPort"]
                    host_ip = container_mapping.get(container_instance)

                    print(f"INFO: Contacting {host_ip}:{host_port} ..")

                    http = urllib3.PoolManager()
                    try:
                        response = http.request(
                            "POST",
                            f"http://{host_ip}:{host_port}/reload",
                            body=json.dumps({"secret": secret}),
                            headers={"Content-Type": "application/json"},
                            timeout=urllib3.Timeout(connect=5, read=60),
                            retries=False,
                        )
                        if response.status == 204:
                            print("INFO: Database reloaded")
                        else:
                            print("ERROR: Failed to reload database")
                    except urllib3.exceptions.NewConnectionError:
                        print("ERROR: Failed to connect to pod")
                    except urllib3.exceptions.ConnectTimeoutError:
                        print("ERROR: Failed to connect to pod")
                    except urllib3.exceptions.ReadTimeoutError:
                        print("ERROR: Failed to connect to pod")


def fetch_container_mapping(cluster):
    container_mapping = {}
    containers = client_ecs.list_container_instances(cluster=cluster)
    containers = client_ecs.describe_container_instances(
        cluster=cluster, containerInstances=containers["containerInstanceArns"]
    )
    for container in containers["containerInstances"]:
        if container["status"] != "ACTIVE":
            continue

        ec2_instances = client_ec2.describe_instances(InstanceIds=[container["ec2InstanceId"]])
        ec2_ip = ec2_instances["Reservations"][0]["Instances"][0]["PrivateIpAddress"]

        container_mapping[container["containerInstanceArn"]] = ec2_ip

    return container_mapping
