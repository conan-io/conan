import tempfile
from unittest import mock

import pytest


@pytest.fixture(autouse=True, scope="package")
def mock_vs_installation_path():
    """
    Integration tests must not require a real Visual Studio installation: they only
    check generated files/commands, never really invoke MSBuild/vcvars. Fake a valid
    installation for every test under this folder, so they behave the same regardless
    of whether VS is actually installed on the machine running them. A test that
    genuinely needs a real VS toolchain belongs in the "functional" tests instead.

    Patching the private ``_vs_installation_path`` covers every caller of the public
    ``vs_installation_path()``/``vs_detect_update()``, however they imported it: both
    look it up through ``detect_vs``'s own globals at call time, not through whichever
    module's copy of the name was used to reach them.

    Scoped to "package" (one patch/undo per test package, not per test) rather than
    "session": test/unittests runs in the same pytest session as test/integration
    whenever the whole suite is invoked as plain ``pytest`` (see testpaths in
    pytest.ini), so a session-wide patch would leak into it. Package scope needs a
    plain ``mock.patch`` instead of the ``monkeypatch`` fixture, which pytest hardcodes
    to function scope only.
    """
    vs_path = tempfile.gettempdir()  # any existing directory works, it's never really used
    with mock.patch("conan.internal.api.detect.detect_vs._vs_installation_path",
                     lambda version: (vs_path, "17.0.00000.0")):
        yield vs_path
