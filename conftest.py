"""Allow the documented ``pytest -q`` command to import the integration.

Home Assistant's test helper imports ``custom_components.lightaway`` from the
working directory, which only ends up on ``sys.path`` when the suite is started
with ``python -m pytest``. Adding the checkout root here keeps the plain
``pytest`` command working as documented.
"""

import sys
from pathlib import Path

ROOT = str(Path(__file__).parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
