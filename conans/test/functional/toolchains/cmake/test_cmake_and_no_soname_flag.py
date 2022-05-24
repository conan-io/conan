import os
import platform
import shutil

import pytest

from conan.tools.env.environment import environment_wrap_command
from conan.tools.files import replace_in_file
from conans.test.assets.pkg_cmake import pkg_cmake, pkg_cmake_app
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Linux", reason="Only Linux")
@pytest.mark.tool("cmake")
@pytest.mark.parametrize("nosoname", [
    True,  # without SONAME
    False  # By default, with SONAME
])
def test_no_soname_flag(nosoname):
    """ This test case is testing this graph structure:
            *   'Executable' -> 'LibB' -> 'LibNoSoname'
        Where:
            *   LibNoSoname: is a package built as shared and without the SONAME flag.
            *   LibB: is a package which requires LibNoSoname.
            *   Executable: is the final consumer building an application and depending on OtherLib.
        How:
            1- Creates LibNoSoname and upload it to remote server
            2- Creates LibB and upload it to remote server
            3- Remove the Conan cache folder
            4- Creates an application and consume LibB
    """
    client = TestClient(default_server_user=True)
    client.save(pkg_cmake("nosoname", "0.1"))
    if nosoname:
        replace_in_file(ConanFileMock(), os.path.join(client.current_folder, "conanfile.py"),
                        'self.cpp_info.libs = ["nosoname"]',
                        'self.cpp_info.libs = ["nosoname"]\n        self.cpp_info.set_property("nosoname", True)')
        replace_in_file(ConanFileMock(), os.path.join(client.current_folder, "CMakeLists.txt"),
                        'target_include_directories(nosoname PUBLIC "include")',
                        'target_include_directories(nosoname PUBLIC "include")\nset_target_properties(nosoname PROPERTIES NO_SONAME 1)')
    client.run("create . -o nosoname/*:shared=True")
    client.save(pkg_cmake("lib_b", "0.1", requires=["nosoname/0.1"]), clean_first=True)
    client.run("create . -o lib_b/*:shared=True -o nosoname/*:shared=True")
    client.save(pkg_cmake_app("app", "0.1", requires=["lib_b/0.1"]), clean_first=True)
    client.run("create . -o nosoname/*:shared=True -o lib_b/*:shared=True")
    client.run("upload * -c -r default")
    shutil.rmtree(client.cache.store)

    client = TestClient(servers=client.servers)
    client.run("install --requires=app/0.1@ -o nosoname*:shared=True -o lib_b/*:shared=True -g VirtualRunEnv")
    # This only finds "app" executable because the "app/0.1" is declaring package_type="application"
    # otherwise, run=None and nothing can tell us if the conanrunenv should have the PATH.
    command = environment_wrap_command("conanrun", "app", cwd=client.current_folder)

    client.run_command(command)
    assert "main: Release!" in client.out
    assert "lib_b: Release!" in client.out
    assert "nosoname: Release!" in client.out
