import os

from conan.tools.files.files import save_toolchain_args
from conan.tools.gnu import Autotools
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.test_files import temp_folder


def test_source_folder_works():
    folder = temp_folder()
    os.chdir(folder)
    save_toolchain_args({
        "configure_args": "-foo bar",
        "make_args": "",
        "autoreconf_args": ""}
    )
    conanfile = ConanFileMock()
    conanfile.folders.set_base_install(folder)
    sources = "/path/to/sources"
    conanfile.folders.set_base_source(sources)
    autotools = Autotools(conanfile)
    autotools.configure(build_script_folder="subfolder")
    assert conanfile.command.replace("\\", "/") == '"/path/to/sources/subfolder/configure" -foo bar '

    autotools = Autotools(conanfile)
    autotools.configure()
    assert conanfile.command.replace("\\", "/") == '"/path/to/sources/configure" -foo bar '
