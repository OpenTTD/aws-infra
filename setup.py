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
        "aws-cdk.core",
    ],

    python_requires=">=3.6",
)
