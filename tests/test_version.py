from importlib.metadata import version as dist_version

from packaging.version import Version

import hotdata_runtime as hr


def test_version_is_valid_pep440():
    Version(hr.__version__)


def test_version_matches_distribution_metadata():
    assert dist_version("hotdata-runtime") == hr.__version__
