import sys
from unittest.mock import patch

import registry


@patch.object(
    sys,
    "argv",
    [
        "setup_registry",
        "--action",
        "setup",
        "--channel",
        "latest/edge",
        "--http-proxy",
        "http://myproxy",
    ],
)
def test_main_setup(setup_registry_fixtures):
    registry.main()


def test_main_push(setup_registry_fixtures, docker_images_json):
    with patch.object(
        sys,
        "argv",
        ["setup_registry", "--action", "push", "--file", docker_images_json],
    ):
        registry.main()
