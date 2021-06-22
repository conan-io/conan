import textwrap

from conan.tools.microsoft.msbuild import msbuild_max_cpu_count_cmd_line_arg
from conans.model.conf import ConfDefinition
from conans.test.utils.mocks import ConanFileMock


def test_tools_build():
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
        tools.build:processes=10
    """))

    conanfile = ConanFileMock()
    conanfile.conf = c.get_conanfile_conf(None)
    max_cpu_count = msbuild_max_cpu_count_cmd_line_arg(conanfile)
    assert max_cpu_count == "/m:10"


def test_tools_ning():
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
        tools.microsoft.msbuild:max_cpu_count=23
    """))

    conanfile = ConanFileMock()
    conanfile.conf = c.get_conanfile_conf(None)
    max_cpu_count = msbuild_max_cpu_count_cmd_line_arg(conanfile)
    assert max_cpu_count == "/m:23"


def test_both_values():
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
        tools.microsoft.msbuild:max_cpu_count=23
        tools.build:processes=10
    """))

    conanfile = ConanFileMock()
    conanfile.conf = c.get_conanfile_conf(None)
    max_cpu_count = msbuild_max_cpu_count_cmd_line_arg(conanfile)
    assert max_cpu_count == "/m:23"


def test_none():
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
    """))

    conanfile = ConanFileMock()
    conanfile.conf = c.get_conanfile_conf(None)
    max_cpu_count = msbuild_max_cpu_count_cmd_line_arg(conanfile)
    assert max_cpu_count is None
