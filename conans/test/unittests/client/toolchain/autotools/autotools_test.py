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
    assert "my_make my_make_args -j23" == runner.command_called

    # test install target argument

    ab.install()
    assert 'my_make install my_make_args DESTDIR=None -j23' == runner.command_called

    ab.install(target="install_other")
    assert 'my_make install_other my_make_args DESTDIR=None -j23' == runner.command_called

    # we can override the number of jobs in the recipe

    ab.make(args=["-j1"])
    assert "-j23" not in runner.command_called
    assert "my_make my_make_args -j1" == runner.command_called

    ab.install(args=["-j1"])
    assert "-j23" not in runner.command_called
    assert "my_make install my_make_args DESTDIR=None -j1" == runner.command_called

    ab.install(args=["DESTDIR=whatever", "-j1"])
    assert "-j23" not in runner.command_called
    assert "my_make install my_make_args DESTDIR=whatever -j1" == runner.command_called
