from infrastructure.https.template import HTTPSTemplateStack


class BinaryProxyStack(HTTPSTemplateStack):
    subdomain_name = "binaries-proxy"
    name = "BinariesProxy"
    image = "openttd/binaries-proxy"
    port = 80
    memory_limit_mib = 128
