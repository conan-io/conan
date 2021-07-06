import textwrap

from conan.tools.google import Bazel
from conans.model.conf import ConfDefinition
from conans.test.utils.mocks import ConanFileMock


def test_bazel_command_with_empty_config():
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
        tools.google.bazel:config=
        tools.google.bazel:bazelrc_path=
    """))

    conanfile = ConanFileMock()
    conanfile.conf = c.get_conanfile_conf(None)

    bazel = Bazel(conanfile)
    bazel.build(label='//test:label')

    assert 'bazel  build  //test:label' == str(conanfile.command)


def test_bazel_command_with_config_values():
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
        tools.google.bazel:config=config
        tools.google.bazel:bazelrc_path=/path/to/bazelrc
    """))

    conanfile = ConanFileMock()
    conanfile.conf = c.get_conanfile_conf(None)

    bazel = Bazel(conanfile)
    bazel.build(label='//test:label')

    assert 'bazel  build  //test:label' == str(conanfile.command)
