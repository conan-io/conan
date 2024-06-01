import pytest

from conan.test.utils.tools import TestClient

@pytest.mark.parametrize('shared', [
    ('False'),
    ('True'),
])
@pytest.mark.tool("qbs")
def test_api_qbs_create_lib(shared):
    client = TestClient()
    client.run("new qbs_lib -d name=hello -d version=1.0")
    client.run("create . -o:h &:shared={shared}".format(shared=shared))
    assert "compiling hello.cpp" in client.out