import os
from mock import patch

from conan.tools.build import save_toolchain_args
from conan.tools.gnu import Autotools
from conan.test.utils.mocks import ConanFileMock
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
    chdir_mock.assert_called_with(autotools, os.path.normpath(os.path.join("/path/to/sources", "subfolder")))

    autotools.autoreconf()
    chdir_mock.assert_called_with(autotools, os.path.normpath("/path/to/sources"))
    assert conanfile.command == 'autoreconf -bar foo'
