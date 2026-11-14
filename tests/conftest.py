"""Home Assistant integration test fixtures.

The Recorder fixture must be prepared before custom integration startup;
otherwise the HA test helper initializes Home Assistant too early.
"""

import pytest


@pytest.fixture(autouse=True)
def _enable_custom_integrations(request):
    if request.node.name in (
        "test_config_flow_and_global_switch",
        "test_calculated_entities_update_from_recorder_result",
    ):
        request.getfixturevalue("recorder_mock")
    request.getfixturevalue("enable_custom_integrations")
