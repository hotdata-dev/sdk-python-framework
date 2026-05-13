import re

from importlib.metadata import version as dist_version

import hotdata_runtime as hr


def test_version_is_pep440_core():
    assert re.fullmatch(r"\d+\.\d+\.\d+(\+.*)?", hr.__version__)


def test_version_matches_distribution_metadata():
    assert dist_version("hotdata-runtime") == hr.__version__
