from infrastructure.https.template import HTTPSTemplateStack


class WebsiteStack(HTTPSTemplateStack):
    subdomain_name = "www"
    name = "Website"
    image = "openttd/website:1.1.18-20191103-1916"
    port = 80
    memory_limit_mib = 128
