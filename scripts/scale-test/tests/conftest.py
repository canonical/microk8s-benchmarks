from tempfile import TemporaryDirectory

import pytest


@pytest.fixture()
def temp_dir():
    with TemporaryDirectory() as dir:
        yield dir
