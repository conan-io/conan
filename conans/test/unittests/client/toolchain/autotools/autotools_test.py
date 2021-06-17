import os

from mock import Mock

from conan.tools import CONAN_TOOLCHAIN_ARGS_FILE
from conan.tools.gnu import Autotools
from conans import ConanFile
from conans.client.tools.files import save
from conans.test.unittests.util.tools_test import RunnerMock
from conans.test.utils.mocks import MockSettings
from conans.test.utils.test_files import temp_folder


def test_configure_triplet_arguments():
    tmp = temp_folder()
    os.chdir(tmp)
    save(CONAN_TOOLCHAIN_ARGS_FILE, """
    {"build": "my_build_flag",
     "host": "my_host_flag",
     "target": "my_target_flag"}
    """)
    runner = RunnerMock()
    conanfile = ConanFile(Mock(), runner=runner)
    conanfile.settings = MockSettings({})
    ab = Autotools(conanfile)
    ab.configure()
    assert "--build=my_build_flag" in runner.command_called
    assert "--host=my_host_flag" in runner.command_called
    assert "--target=my_target_flag" in runner.command_called

    save(CONAN_TOOLCHAIN_ARGS_FILE, """
        {"build": "my_build_flag",
         "host": "my_host_flag"}
        """)
    ab = Autotools(conanfile)
    ab.configure()
    assert "--build=my_build_flag" in runner.command_called
    assert "--host=my_host_flag" in runner.command_called
    assert "--target=my_target_flag" not in runner.command_called


def test_configure_triplet_arguments_already_defined():
    tmp = temp_folder()
    os.chdir(tmp)
    save(CONAN_TOOLCHAIN_ARGS_FILE, """
        {"build": "my_build_flag",
         "host": "my_host_flag",
         "target": "my_target_flag"}
        """)
    runner = RunnerMock()
    conanfile = ConanFile(Mock(), runner=runner)
    conanfile.settings = MockSettings({})
    ab = Autotools(conanfile)
    ab.configure(args=["--build=my_override_build", "--host=my_override_host"])
    assert "--build=my_build_flag" not in runner.command_called
    assert "--host=my_host_flag" not in runner.command_called

    assert "--build=my_override_build" in runner.command_called
    assert "--host=my_override_host" in runner.command_called
    assert "--target=my_target_flag" in runner.command_called


def test_configure_install_dirs():
    runner = RunnerMock()
    conanfile = ConanFile(Mock(), runner=runner)
    conanfile.settings = MockSettings({})
    conanfile.package_folder = "/package_folder"
    # Package folder is not defined
    ab = Autotools(conanfile)
    ab.configure()
    assert "--prefix" not in runner.command_called
    assert "--bindir" not in runner.command_called
    assert "--libdir" not in runner.command_called
    assert "--includedir" not in runner.command_called
    assert "--datarootdir" not in runner.command_called

    # package folder defined
    ab.configure(default_install_args=True)
    assert "--prefix=/package_folder" in runner.command_called
    assert "--bindir" in runner.command_called
    assert "--libdir" in runner.command_called
    assert "--includedir" in runner.command_called
    assert "--datarootdir" in runner.command_called

    #  User can always declare by hand the needed flags
    args = ["--prefix=%s" % conanfile.package_folder,
            "--includedir=${prefix}/include"]
    ab.configure(args=args)
    assert "--prefix=/package_folder" in runner.command_called
    assert "--includedir" in runner.command_called
    assert "--datarootdir" not in runner.command_called
    assert "--libdir" not in runner.command_called

    # If the user mixes the automatic with manual is his fault
    ab.configure(default_install_args=True, args=args)
    assert runner.command_called.count("--prefix") == 2
