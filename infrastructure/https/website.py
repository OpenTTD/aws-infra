from infrastructure.https.template import HTTPSTemplateStack


class WebsiteStack(HTTPSTemplateStack):
    subdomain_name = "www"
    name = "Website"
    image = "openttd/website"
    port = 80
    memory_limit_mib = 128
