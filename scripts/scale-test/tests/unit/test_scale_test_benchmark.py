import os

from benchmarklib.models import DockerCredentials
from scale_test.benchmark import get_docker_credentials


def test_get_docker_credentials():
    assert get_docker_credentials() is None

    os.environ["DOCKER_USERNAME"] = "foo"
    os.environ["DOCKER_PASSWORD"] = "bar"

    assert get_docker_credentials() == DockerCredentials(username="foo", password="bar")

    os.environ.pop("DOCKER_USERNAME")
    os.environ.pop("DOCKER_PASSWORD")
