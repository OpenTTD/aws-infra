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

    package_dir={"": "infrastructure"},
    packages=setuptools.find_packages(where="infrastructure"),

    install_requires=[
        "aws-cdk.aws-certificatemanager",
        "aws-cdk.aws-ecs",
        "aws-cdk.aws-elasticloadbalancingv2",
        "aws-cdk.aws-logs",
        "aws-cdk.aws-route53",
        "aws-cdk.aws-s3",
        "aws-cdk.aws-ssm",
        "aws-cdk.core",
    ],

    python_requires=">=3.6",
)
