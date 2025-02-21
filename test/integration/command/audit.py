from mock import mock
from mock.mock import PropertyMock

from conan.test.utils.tools import TestClient, GenConanfile


def test_initial_proxy_workflow():
    tc  = TestClient(light=True)
    tc.save({"conanfile.py": GenConanfile("zlib", "1.2.11")})
    tc.run("export .")

    tc.run("audit scan --requires=zlib/1.2.11", assert_error=True)
    assert "Missing authentication token" in tc.out

    tc.run("audit provider --auth --name conancenter --token 1234")

    # TODO: The rest of the code needs to mock the connection not to actually connect to the server
