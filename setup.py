import setuptools


with open("README.md") as fp:
    long_description = fp.read()


setuptools.setup(
    name="OpenTTD IaC",
    version="1.0",

    description="OpenTTD - Infrastructure as Code",
    long_description=long_description,
    long_description_content_type="text/markdown",

    author="TrueBrain",

    package_dir={"": "openttd"},
    packages=setuptools.find_packages(where="openttd"),

    install_requires=[
        "aws-cdk.aws-certificatemanager",
        "aws-cdk.aws-ecs",
        "aws-cdk.aws-elasticloadbalancingv2",
        "aws_cdk.aws_events_targets",
        "aws-cdk.aws-logs",
        "aws-cdk.aws-route53",
        "aws-cdk.aws-s3",
        "aws-cdk.aws-ssm",
        "aws-cdk.core",
        "aws-cdk.custom-resources",
        "boto3",
    ],

    python_requires=">=3.6",
)
