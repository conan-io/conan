import os

from conan.tools.build import save_toolchain_args
from conan.tools.gnu import Autotools
from conan import ConanFile
from conans.model.conf import Conf
from test.unittests.util.tools_test import RunnerMock
from conan.test.utils.mocks import MockSettings
from conan.test.utils.test_files import temp_folder


def test_configure_arguments():
    tmp = temp_folder()
    os.chdir(tmp)
    save_toolchain_args({
        "configure_args": "my_configure_args",
        "make_args": "my_make_args"}
    )
    runner = RunnerMock()
    conanfile = ConanFile()
    conanfile.run = runner
    conanfile.settings = MockSettings({"os": "Linux"})
    conanfile.settings_build = conanfile.settings
    conanfile.folders.set_base_source(tmp)
    conanfile.conf = Conf()
    conanfile.conf.define("tools.gnu:make_program", "my_make")
    conanfile.conf.define("tools.build:jobs", 23)
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

    for make_args in ["my_make_args", ""]:

        save_toolchain_args({
            "configure_args": "my_configure_args",
            "make_args": f"{make_args}"}
        )

        ab = Autotools(conanfile)

        make_args_str = f" {make_args}" if make_args else ""

        ab.make(args=["-j1"])
        assert "-j23" not in runner.command_called
        assert f"my_make{make_args_str} -j1" == runner.command_called

        ab.install(args=["-j1"])
        assert "-j23" not in runner.command_called
        assert f"my_make install{make_args_str} DESTDIR=None -j1" == runner.command_called

        ab.install(args=["DESTDIR=whatever", "-j1"])
        assert "-j23" not in runner.command_called
        assert f"my_make install{make_args_str} DESTDIR=whatever -j1" == runner.command_called

        ab.install(args=["DESTDIR=whatever", "-arg1 -j1 -arg2"])
        assert "-j23" not in runner.command_called
        assert f"my_make install{make_args_str} DESTDIR=whatever -arg1 -j1 -arg2" == runner.command_called

        # check that we don't detect -j in an argument as number of jobs
        ab.install(args=["DESTDIR=/user/smith-john/whatever"])
        assert f"my_make install{make_args_str} DESTDIR=/user/smith-john/whatever -j23" == runner.command_called

        # check that we don't detect -j in an argument as number of jobs
        ab.install(args=["DESTDIR=/user/smith-j47/whatever"])
        assert f"my_make install{make_args_str} DESTDIR=/user/smith-j47/whatever -j23" == runner.command_called
