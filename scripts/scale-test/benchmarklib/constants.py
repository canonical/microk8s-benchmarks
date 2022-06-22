from enum import Enum

DEFAULT_ADD_NODE_TOKEN = "microk8sisgreatushouldgiveitatry"
YEAR = 60 * 60 * 24 * 365
DEFAULT_ADD_NODE_TOKEN_TTL = 5 * YEAR


class KnownRegistries(Enum):
    """
    Known container registries
    """

    DOCKER = "docker.io"
    QUAY = "quay.io"
    K8S = "k8s.gcr.io"
