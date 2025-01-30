import pytest

from conan.internal.workspace import Workspace
from conan.test.utils.tools import TestClient


Workspace.TEST_ENABLED = "will_break_next"


@pytest.mark.tool("cmake")
def test():
    c = TestClient()
    c.run("new cmake_lib -d name=mymath")
    c.run("create . -tf=")

    c.save({}, clean_first=True)
    c.run("new workspace -d requires=mymath/0.1")
    c.run("workspace build")
    # it works without failing

