import sys
from unittest.mock import patch

import registry


@patch.object(
    sys,
    "argv",
    [
        "setup_registry",
        "setup",
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
        ["setup_registry", "push", "--file", docker_images_json],
    ):
        registry.main()
