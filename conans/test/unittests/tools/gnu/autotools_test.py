import os

from conan.tools.files.files import save_toolchain_args
from conan.tools.gnu import Autotools
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.test_files import temp_folder
from conans.util.files import mkdir


def test_source_folder_works():
    folder = temp_folder()
    generators_folder = os.path.join(folder, "build", "generators")
    mkdir(generators_folder)
    os.chdir(generators_folder)
    save_toolchain_args({
        "configure_args": "-foo bar",
        "make_args": ""}
    )
    conanfile = ConanFileMock()
    sources = "/path/to/sources"
    conanfile.folders.set_base_source(sources)
    conanfile.folders.set_base_generators(folder)
    autotools = Autotools(conanfile, build_script_folder="subfolder")
    autotools.configure()
    assert conanfile.command.replace("\\", "/") == '"/path/to/sources/subfolder/configure" -foo bar'

    autotools = Autotools(conanfile)
    autotools.configure()
    assert conanfile.command.replace("\\", "/") == '"/path/to/sources/configure" -foo bar'
