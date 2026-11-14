"""Home Assistant integration test fixtures.

The Recorder fixture must be prepared before custom integration startup;
otherwise the HA test helper initializes Home Assistant too early. Tests that
need the recorder database mark themselves with ``@pytest.mark.recorder_db``.
"""

import pytest


@pytest.fixture(autouse=True)
def _enable_custom_integrations(request):
    if request.node.get_closest_marker("recorder_db"):
        request.getfixturevalue("recorder_mock")
    request.getfixturevalue("enable_custom_integrations")
