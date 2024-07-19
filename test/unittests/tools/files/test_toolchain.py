import os
import textwrap

import pytest

from conan.tools.build import load_toolchain_args, save_toolchain_args, CONAN_TOOLCHAIN_ARGS_FILE, \
    CONAN_TOOLCHAIN_ARGS_SECTION
from conans.errors import ConanException
from conan.test.utils.test_files import temp_folder
from conans.util.files import save, load


def test_load_empty_toolchain_args_in_default_dir():
    folder = temp_folder()
    os.chdir(folder)
    save(CONAN_TOOLCHAIN_ARGS_FILE, "[%s]" % CONAN_TOOLCHAIN_ARGS_SECTION)
    config = load_toolchain_args()
    assert not config


def test_load_toolchain_args_if_it_does_not_exist():
    folder = temp_folder()
    os.chdir(folder)
    with pytest.raises(ConanException):
        load_toolchain_args()


def test_toolchain_args_with_content_full():
    folder = temp_folder()
    content = textwrap.dedent(r"""
    [%s]
    win_path=my\win\path
    command=conan --option "My Option"
    my_regex=([A-Z])\w+
    """ % CONAN_TOOLCHAIN_ARGS_SECTION)
    save(os.path.join(folder,  CONAN_TOOLCHAIN_ARGS_FILE), content)
    args = load_toolchain_args(generators_folder=folder)
    assert args["win_path"] == r'my\win\path'
    assert args["command"] == r'conan --option "My Option"'
    assert args["my_regex"] == r'([A-Z])\w+'


def test_save_toolchain_args_empty():
    folder = temp_folder()
    content = {}
    save_toolchain_args(content, generators_folder=folder)
    args = load(os.path.join(folder, CONAN_TOOLCHAIN_ARGS_FILE))
    assert "[%s]" % CONAN_TOOLCHAIN_ARGS_SECTION in args


def test_save_toolchain_args_full():
    folder = temp_folder()
    content = {
        'win_path': r'my\win\path',
        'command': r'conan --option "My Option"',
        'my_regex': r'([A-Z])\w+'
    }
    save_toolchain_args(content, generators_folder=folder)
    args = load(os.path.join(folder, CONAN_TOOLCHAIN_ARGS_FILE))
    assert "[%s]" % CONAN_TOOLCHAIN_ARGS_SECTION in args
    assert r'win_path = my\win\path' in args
