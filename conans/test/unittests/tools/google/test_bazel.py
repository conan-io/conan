import textwrap
import os
from conan.tools import CONAN_TOOLCHAIN_ARGS_SECTION, CONAN_TOOLCHAIN_ARGS_FILE
from conans.util.files import save, remove

from conan.tools.google import Bazel
from conans.model.conf import ConfDefinition
from conans.test.utils.mocks import ConanFileMock


def test_bazel_command_with_empty_config():
    conanfile = ConanFileMock()
    args_file = os.path.join(conanfile.generators_folder, CONAN_TOOLCHAIN_ARGS_FILE)
    save(args_file,
         textwrap.dedent("""\
            [%s]
            bazel_configs=
            bazelrc_path=
            """ % CONAN_TOOLCHAIN_ARGS_SECTION))

    bazel = Bazel(conanfile)
    bazel.build(label='//test:label')
    # TODO: Create a context manager to remove the file
    remove(args_file)
    assert 'bazel  build  //test:label' == str(conanfile.command)


def test_bazel_command_with_config_values():
    conanfile = ConanFileMock()
    args_file = os.path.join(conanfile.generators_folder, CONAN_TOOLCHAIN_ARGS_FILE)
    save(args_file,
         textwrap.dedent("""\
            [%s]
            bazel_configs=config,config2
            bazelrc_path=/path/to/bazelrc
            """ % CONAN_TOOLCHAIN_ARGS_SECTION))
    bazel = Bazel(conanfile)
    bazel.build(label='//test:label')
    # TODO: Create a context manager to remove the file
    remove(args_file)
    assert 'bazel --bazelrc=/path/to/bazelrc build --config=config --config=config2 //test:label' == str(conanfile.command)
