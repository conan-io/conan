from mock import mock

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conan.test.utils.env import environment_update


def test_package_revision_latest():
    # https://github.com/conan-io/conan/issues/14945
    c = TestClient()
    c.save({"tool/conanfile.py": GenConanfile("tool", "0.1").with_package_file("file.txt",
                                                                               env_var="MYVAR"),
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_tool_requires("tool/0.1")})
    with environment_update({"MYVAR": "MYVALUE1"}):
        # Just in case dates were not correctly processed
        with mock.patch("conan.internal.cache.cache.revision_timestamp_now",
                        return_value="1691760295"):
            c.run("create tool")
    prev1 = c.created_package_revision("tool/0.1")
    with environment_update({"MYVAR": "MYVALUE2"}):
        # Just in case dates were not correctly processed
        with mock.patch("conan.internal.cache.cache.revision_timestamp_now",
                        return_value="1697442658"):
            c.run("create tool")
    prev2 = c.created_package_revision("tool/0.1")

    c.run("create pkg")
    # The latest is used
    assert prev2 in c.out
    assert prev1 not in c.out

    c.run("install --requires=pkg/0.1 --build=pkg*")
    # The latest is used
    assert prev2 in c.out
    assert prev1 not in c.out
