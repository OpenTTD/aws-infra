#!/usr/bin/env python3

import os

from aws_cdk import core

from infrastructure.core.core import CoreStack
from infrastructure.core.https_listener import HTTPSListenerStack
from infrastructure.https.binaries_proxy import BinaryProxyStack
from infrastructure.https.default_backend import DefaultBackendStack
from infrastructure.https.website import WebsiteStack
from infrastructure.enumeration import EnvType


env = {
    "region": "eu-central-1",
    "account": os.getenv('AWS_ACCOUNT_ID'),
}

env_type = EnvType.DEVELOPMENT
hosted_zone = "openttd.org"
domain_name = "aws.openttd.org"


app = core.App()

core = CoreStack(app, f"{env_type.value}-Core",
    env=env,
)
https_listener = HTTPSListenerStack(app, f"{env_type.value}-Listener",
    core=core,
    hosted_zone_name=hosted_zone,
    domain_name=domain_name,
    env=env,
)


https_kwargs = {
    "core": core,
    "https_listener": https_listener,
    "env": env,
}
DefaultBackendStack(app, f"{env_type.value}-Default", **https_kwargs)
WebsiteStack(app, f"{env_type.value}-Website", **https_kwargs)
BinaryProxyStack(app, f"{env_type.value}-BinariesProxy", **https_kwargs)


app.synth()
