import textwrap

import pytest

from conan.tools.cmake.cmake import _cmake_cmd_line_args
from conans.model.conf import ConfDefinition
from conans.test.utils.mocks import ConanFileMock


@pytest.fixture
def conanfile():
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
        tools.build:jobs=10
    """))

    conanfile = ConanFileMock()
    conanfile.conf = c.get_conanfile_conf(None)
    return conanfile


def test_no_generator(conanfile):
    args = _cmake_cmd_line_args(conanfile, None, parallel=True)
    assert not len(args)


def test_makefiles(conanfile):
    args = _cmake_cmd_line_args(conanfile, 'Unix Makefiles', parallel=True)
    assert args == ['-j40']

    args = _cmake_cmd_line_args(conanfile, 'Unix Makefiles', parallel=False)
    assert not len(args)

    args = _cmake_cmd_line_args(conanfile, 'NMake Makefiles', parallel=True)
    assert not len(args)


def test_ninja(conanfile):
    args = _cmake_cmd_line_args(conanfile, 'Ninja', parallel=True)
    assert ['-j30'] == args

    args = _cmake_cmd_line_args(conanfile, 'Ninja', parallel=False)
    assert not len(args)


def test_visual_studio(conanfile):
    args = _cmake_cmd_line_args(conanfile, 'Visual Studio 16 2019', parallel=True)
    assert ['/m:20'] == args

    args = _cmake_cmd_line_args(conanfile, 'Ninja', parallel=False)
    assert not len(args)
