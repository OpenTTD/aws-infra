# AWS Infrastructure

This repository contains the AWS infrastructure OpenTTD is running for all its online services.
It is build with AWS CDK.

## Usage

This is an AWS CDK project. Please refer to the CDK manual to read up how to use this repository.

Running this project will deploy the full infrastructure as used by OpenTTD into your AWS account; mind you that provisioning certificates will fail as you lack the verification to create those.
For this change `hosted_zone_name` in `app.py` to a domain you do have control over.

There are two maturity versions of this: a development version (on by default) and a live version.
The first is used to test out new features.

Every maturity version has two deployment versions of this: a staging and a production version.
The first is commonly used to try out changes before they are being pushed to production.
This has to do with the common deployment flow (see below).

Secrets are not part of this repository; on `cdk synth` you will be told which secrets to created in the AWS SSM Parameter Store (as a Secret).

### Common Deployment flow

#### Staging deployments
1. A new commit is pushed to `master` of a repository.
1. GitHub Actions create a new image and publishes this on GitHub Registry.
1. GitHub Actions updates the Systems Manager Parameter Store with new tag.
1. GitHub Actions triggers a redeploy of the staging version on CloudFormation.

#### Production deployments
1. A commit is tagged.
1. GitHub Actions create a new image and publishes this on GitHub Registry.
1. GitHub Actions updates the Systems Manager Parameter Store with new tag.
1. GitHub Actions triggers a redeploy of the production version on CloudFormation.

## Found a security issue?

Please report any security-related issue with this repository or the infrastructure on AWS to truebrain@openttd.org.
