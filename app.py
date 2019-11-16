#!/usr/bin/env python3

from aws_cdk import core

from infrastructure.website.stack import WebsiteStack


app = core.App()
WebsiteStack(app, "website", env={"region": "eu-central-1"})

app.synth()
