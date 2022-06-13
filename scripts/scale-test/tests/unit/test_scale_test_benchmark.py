import os

from benchmarklib.models import DockerCredentials
from scale_test.benchmark import Process, get_docker_credentials, valid_cluster_shapes


def test_valid_cluster_shapes():
    for control_plane, total in valid_cluster_shapes():
        assert total >= control_plane


def test_get_docker_credentials():
    assert get_docker_credentials() is None

    os.environ["DOCKER_USERNAME"] = "foo"
    os.environ["DOCKER_PASSWORD"] = "bar"

    assert get_docker_credentials() == DockerCredentials(username="foo", password="bar")

    os.environ.pop("DOCKER_USERNAME")
    os.environ.pop("DOCKER_PASSWORD")


def test_Process():
    def target():
        raise ValueError("foobar")

    p = Process(target=target, args=())
    p.start()
    p.join()

    assert p.exception is not None
    assert isinstance(p.exception[0], ValueError)
    assert isinstance(p.exception[1], str)
