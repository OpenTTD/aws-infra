#!/usr/bin/env python3

import os

from aws_cdk import core
from aws_cdk.core import (
    App,
    Tag,
)

from infrastructure.core.core import CoreStack
from infrastructure.core.certificate import CertificateStack
from infrastructure.core.listener_https import ListenerHTTPSStack
from infrastructure.core.parameter_store import ParameterStoreStack
from infrastructure.https.binaries_proxy import BinaryProxyStack
from infrastructure.https.default_backend import DefaultBackendStack
from infrastructure.https.website import WebsiteStack
from infrastructure.enumeration import EnvType


env_type = EnvType.DEVELOPMENT

env = {
    "region": "eu-central-1",
    "account": os.getenv('AWS_ACCOUNT_ID'),
}
hosted_zone = "openttd.org"

if env_type == EnvType.PRODUCTION:
    domain_names = {
        False: "openttd.org",
        True: "staging.openttd.org",
    }
else:
    domain_names = {
        False: "aws.openttd.org",
        True: "staging.aws.openttd.org",
    }

app = App()
Tag.add(app, "Env", env_type.value)

parameter_store = ParameterStoreStack(app, f"{env_type.value}-ParameterStore",
    env=env,
)
certificate = CertificateStack(app, f"{env_type.value}-Certificate",
    hosted_zone_name=hosted_zone,
    env=env,
)
core = CoreStack(app, f"{env_type.value}-Core",
    env=env,
)

listener_https = ListenerHTTPSStack(app, f"{env_type.value}-Listener-HTTPS",
    core=core,
    certificate=certificate,
    env=env,
)

certificate.set_current_domain_name(domain_names[False])
https_kwargs = {
    "core": core,
    "listener_https": listener_https,
    "parameter_store": parameter_store,
    "is_staging": False,
    "env": env,
}
DefaultBackendStack(app, f"{env_type.value}-DefaultBackend", **https_kwargs)


for is_staging in (True, False):
    if is_staging:
        prefix = f"{env_type.value}-Staging-"
    else:
        prefix = f"{env_type.value}-Production-"

    certificate.set_current_domain_name(domain_names[is_staging])
    https_kwargs["is_staging"] = is_staging

    WebsiteStack(app, f"{prefix}Website", **https_kwargs)
    BinaryProxyStack(app, f"{prefix}BinariesProxy", **https_kwargs)


app.synth()
