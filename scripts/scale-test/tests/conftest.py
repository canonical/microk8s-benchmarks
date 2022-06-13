from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest


@pytest.fixture()
def temp_dir():
    with TemporaryDirectory() as dir:
        yield dir


@pytest.fixture()
def path_cwd_mock(temp_dir):
    # Prevents safe_cluster_info from cluttering
    # local filesystem with dummy cluster json data
    temp_dir_path = Path(temp_dir)
    with patch.object(Path, "cwd", return_value=temp_dir_path):
        yield
