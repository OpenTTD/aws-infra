from infrastructure.https.template import HTTPSTemplateStack


class DefaultBackendStack(HTTPSTemplateStack):
    default = True
    name = "DefaultBackend"
    image = "truebrain/default-backend:1"
    port = 80
    memory_limit_mib = 128
