import os

from mock import Mock

from conan.tools.files.files import save_toolchain_args
from conan.tools.gnu import Autotools
from conans import ConanFile
from conans.model.conf import Conf
from conans.test.unittests.util.tools_test import RunnerMock
from conans.test.utils.mocks import MockSettings
from conans.test.utils.test_files import temp_folder


def test_configure_arguments():
    tmp = temp_folder()
    os.chdir(tmp)
    save_toolchain_args({
        "configure_args": "my_configure_args",
        "make_args": "my_make_args"}
    )
    runner = RunnerMock()
    conanfile = ConanFile(Mock(), runner=runner)
    conanfile.settings = MockSettings({})
    conanfile.folders.set_base_install(tmp)
    conanfile.folders.set_base_source(tmp)
    conanfile.conf = Conf()
    conanfile.conf["tools.gnu:make_program"] = "my_make"
    conanfile.conf["tools.build:jobs"] = 23
    ab = Autotools(conanfile)
    ab.configure()
    assert "configure\" my_configure_args" in runner.command_called

    ab = Autotools(conanfile)
    ab.make()
    assert "my_make my_make_args -j23" in runner.command_called

