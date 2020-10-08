import boto3
import os

from collections import defaultdict

client_ecs = None
client_ec2 = None


def write_nginx_config(load_balancer):
    with open(f"nlb.conf", "w") as fp:
        fp.write(f"stream {{\n")

        for listener, backends in load_balancer.items():
            protocol, port = listener

            if protocol == "tcp":
                protocol_if_not_tcp = ""
            else:
                protocol_if_not_tcp = protocol

            fp.write(f"  upstream {protocol}{port} {{\n")
            fp.write(f"    hash $remote_addr;\n")
            for backend in backends:
                host_ip, host_port = backend
                fp.write(f"    server {host_ip}:{host_port};\n")
            fp.write(f"  }}\n")

            fp.write(f"  server {{\n")
            fp.write(f"    listen {port} {protocol_if_not_tcp};\n")
            fp.write(f"    listen [::]:{port} {protocol_if_not_tcp};\n")
            fp.write(f"    proxy_pass {protocol}{port};\n")
            fp.write(f"    proxy_protocol on;\n")
            if protocol == "udp":
                fp.write(f"    proxy_requests 1;\n")
                fp.write(f"    proxy_timeout 30s;\n")
            fp.write(f"  }}\n")

        fp.write(f"}}\n")

    os.system("systemctl reload nginx")


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


def fetch_active_tasks(cluster, container_mapping):
    load_balancer = defaultdict(set)

    services = client_ecs.list_services(cluster=cluster, maxResults=100)
    for service in services["serviceArns"]:
        tags = client_ecs.list_tags_for_resource(resourceArn=service)
        tags = {tag["key"]: tag["value"] for tag in tags["tags"]}

        protocol = tags.get("NLB-protocol")
        port = tags.get("NLB-port")

        if not protocol or not port:
            continue

        port = int(port)

        tasks = client_ecs.list_tasks(cluster=cluster, serviceName=service)
        tasks = client_ecs.describe_tasks(cluster=cluster, tasks=tasks["taskArns"])

        for task in tasks["tasks"]:
            if task["lastStatus"] != "RUNNING" or task["desiredStatus"] != "RUNNING":
                continue

            container_instance = task["containerInstanceArn"]
            for container in task["containers"]:
                for network_binding in container["networkBindings"]:
                    if network_binding["containerPort"] == port:
                        host_port = network_binding["hostPort"]

                        load_balancer[(protocol, port)].add((container_mapping.get(container_instance), host_port))

    return load_balancer


def main():
    global client_ec2, client_ecs

    region = os.environ.get("NLB_REGION")
    if not region:
        with open("/etc/.region", "r") as fp:
            region = fp.read().strip()

    cluster = os.environ.get("NLB_CLUSTER")
    if not cluster:
        with open("/etc/.cluster", "r") as fp:
            cluster = fp.read().strip()

    client_ecs = boto3.client("ecs", region_name=region)
    client_ec2 = boto3.client("ec2", region_name=region)

    container_mapping = fetch_container_mapping(cluster)
    load_balancer = fetch_active_tasks(cluster, container_mapping)

    write_nginx_config(load_balancer)


if __name__ == "__main__":
    main()
