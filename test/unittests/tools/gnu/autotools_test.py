import pytest
import os
from mock import patch

from conan.tools.build import save_toolchain_args
from conan.tools.gnu import Autotools
from conan.test.utils.mocks import ConanFileMock, MockSettings
from conan.test.utils.test_files import temp_folder


@patch('conan.tools.gnu.autotools.chdir')
def test_source_folder_works(chdir_mock):
    folder = temp_folder()
    os.chdir(folder)
    save_toolchain_args({
        "configure_args": "-foo bar",
        "make_args": "",
        "autoreconf_args": "-bar foo"}
    )
    conanfile = ConanFileMock()
    sources = "/path/to/sources"
    conanfile.folders.set_base_source(sources)
    autotools = Autotools(conanfile)
    autotools.configure(build_script_folder="subfolder")
    assert conanfile.command.replace("\\", "/") == '"/path/to/sources/subfolder/configure" -foo bar '

    autotools = Autotools(conanfile)
    autotools.configure()
    assert conanfile.command.replace("\\", "/") == '"/path/to/sources/configure" -foo bar '

    autotools.autoreconf(build_script_folder="subfolder")
    chdir_mock.assert_called_with(autotools,
                                  os.path.normpath(os.path.join("/path/to/sources", "subfolder")))

    autotools.autoreconf()
    chdir_mock.assert_called_with(autotools, os.path.normpath("/path/to/sources"))
    assert conanfile.command == 'autoreconf -bar foo'


@pytest.mark.parametrize("install_strip", [False, True])
def test_install_strip(install_strip):
    """
    When the configuration `tools.build:install_strip` is set to True,
    the Autotools install command should invoke the `install-strip` target.
    """
    folder = temp_folder()
    os.chdir(folder)
    save_toolchain_args({})
    settings = MockSettings({"build_type": "Release",
                             "compiler": "gcc",
                             "compiler.version": "7",
                             "os": "Linux",
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.conf.define("tools.build:install_strip", install_strip)
    conanfile.folders.generators = "."

    autotools = Autotools(conanfile)
    autotools.install()

    assert ('install-strip' in str(conanfile.command)) == install_strip
