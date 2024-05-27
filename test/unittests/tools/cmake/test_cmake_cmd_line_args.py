import textwrap

import pytest

from conan.tools.cmake.cmake import _cmake_cmd_line_args
from conans.model.conf import ConfDefinition
from conan.test.utils.mocks import ConanFileMock


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
    args = _cmake_cmd_line_args(conanfile, None)
    assert not len(args)


def test_makefiles(conanfile):
    args = _cmake_cmd_line_args(conanfile, 'Unix Makefiles')
    assert args == ['-j10']

    args = _cmake_cmd_line_args(conanfile, 'NMake Makefiles')
    assert not len(args)


def test_ninja(conanfile):
    args = _cmake_cmd_line_args(conanfile, 'Ninja')
    assert ['-j10'] == args


def test_visual_studio(conanfile):
    args = _cmake_cmd_line_args(conanfile, 'Visual Studio 16 2019')
    assert [] == args

    args = _cmake_cmd_line_args(conanfile, 'Ninja')
    assert args == ['-j10']
