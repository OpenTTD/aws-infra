from enum import Enum


class Maturity(Enum):
    DEVELOPMENT = "Dev"
    PRODUCTION = "Live"


class Deployment(Enum):
    STAGING = "Staging"
    PRODUCTION = "Production"
