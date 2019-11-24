from infrastructure.https.template import HTTPSTemplateStack


class BinaryProxyStack(HTTPSTemplateStack):
    subdomain_name = "binaries-proxy"
    name = "BinariesProxy"
    image = "openttd/binaries-proxy:1.0.1-20191102-0700"
    port = 80
    memory_limit_mib = 128
