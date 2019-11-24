# OpenTTD's Infrastructure as Code

This contains all the code used by OpenTTD to deploy the infrastructure.

## Usage

This is an AWS CDK project. Please refer to the CDK manual to read up how to
use this repository.

## Deployment flow

1) GitHub Actions create a new image and publishes this on GitHub Registry.
2) GitHub Actions updates the Systems Manager Parameter Store with new tag.
3) GitHub Actions triggers a redeploy of the CloudFormation.

This triggers a rolling upgrade to the new version.
