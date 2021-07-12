import os
import tempfile
import textwrap

import pytest
from conans import load

from conan.tools import CONAN_TOOLCHAIN_ARGS_FILE, CONAN_TOOLCHAIN_ARGS_SECTION
from conan.tools.files import load_toolchain_args, save_toolchain_args
from conans.errors import ConanException
from conans.util.files import save, remove


def test_load_empty_toolchain_args_in_default_dir():
    save(CONAN_TOOLCHAIN_ARGS_FILE, "[%s]" % CONAN_TOOLCHAIN_ARGS_SECTION)
    try:
        config = load_toolchain_args()
        assert not config
    finally:
        remove(CONAN_TOOLCHAIN_ARGS_FILE)


def test_load_toolchain_args_if_it_does_not_exist():
    with pytest.raises(ConanException):
        load_toolchain_args()


def test_toolchain_args_with_content_full():
    temp_folder = tempfile.mkdtemp()
    content = textwrap.dedent(r"""
    [%s]
    win_path=my\win\path
    command=conan --option "My Option"
    my_regex=([A-Z])\w+
    """ % CONAN_TOOLCHAIN_ARGS_SECTION)
    save(os.path.join(temp_folder,  CONAN_TOOLCHAIN_ARGS_FILE), content)
    args = load_toolchain_args(generators_folder=temp_folder)
    assert args["win_path"] == r'my\win\path'
    assert args["command"] == r'conan --option "My Option"'
    assert args["my_regex"] == r'([A-Z])\w+'


def test_save_toolchain_args_empty():
    temp_folder = tempfile.mkdtemp()
    content = {}
    save_toolchain_args(content, generators_folder=temp_folder)
    args = load(os.path.join(temp_folder, CONAN_TOOLCHAIN_ARGS_FILE))
    assert "[%s]" % CONAN_TOOLCHAIN_ARGS_SECTION in args


def test_save_toolchain_args_full():
    temp_folder = tempfile.mkdtemp()
    content = {
        'win_path': r'my\win\path',
        'command': r'conan --option "My Option"',
        'my_regex': r'([A-Z])\w+'
    }
    save_toolchain_args(content, generators_folder=temp_folder)
    args = load(os.path.join(temp_folder, CONAN_TOOLCHAIN_ARGS_FILE))
    assert "[%s]" % CONAN_TOOLCHAIN_ARGS_SECTION in args
    assert r'win_path = my\win\path' in args
