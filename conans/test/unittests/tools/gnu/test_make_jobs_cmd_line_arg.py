import textwrap

from conan.tools.gnu.make import make_jobs_cmd_line_arg
from conans.model.conf import ConfDefinition
from conans.test.utils.mocks import ConanFileMock


def test_tools_build():
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
        tools.build:processes=10
    """))

    conanfile = ConanFileMock()
    conanfile.conf = c.get_conanfile_conf(None)
    njobs = make_jobs_cmd_line_arg(conanfile)
    assert njobs == "-j10"


def test_tools_gnu_make():
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
        tools.gnu.make:jobs=23
    """))

    conanfile = ConanFileMock()
    conanfile.conf = c.get_conanfile_conf(None)
    njobs = make_jobs_cmd_line_arg(conanfile)
    assert njobs == "-j23"


def test_both_values():
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
        tools.gnu.make:jobs=23
        tools.build:processes=10
    """))

    conanfile = ConanFileMock()
    conanfile.conf = c.get_conanfile_conf(None)
    njobs = make_jobs_cmd_line_arg(conanfile)
    assert njobs == "-j23"


def test_none():
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
    """))

    conanfile = ConanFileMock()
    conanfile.conf = c.get_conanfile_conf(None)
    njobs = make_jobs_cmd_line_arg(conanfile)
    assert njobs is None
