import os
from pathlib import Path

from conan.internal.paths import get_conan_user_home
from conan.test.utils.test_files import temp_folder
from conans.util.files import chdir


def test_conanrc_abs_path_get_conan_user_home():
    _temp_folder = temp_folder(path_with_spaces=True)
    folder_conan_runs = os.path.join(_temp_folder, "folder_where_conan_runs")
    os.mkdir(folder_conan_runs)
    with open(os.path.join(_temp_folder, ".conanrc"), 'w+') as file:
        file.write(f'conan_home={_temp_folder}\n')
    with chdir(folder_conan_runs):
        conan_home = get_conan_user_home()
        assert _temp_folder == conan_home


def test_conanrc_local_path_get_conan_user_home():
    _temp_folder = temp_folder(path_with_spaces=True)
    subfolder = "subfolder inside temp"
    with chdir(_temp_folder):
        with open(os.path.join(_temp_folder, ".conanrc"), 'w+') as file:
            file.write(f'conan_home=.{os.sep}{subfolder}\n')
        conan_home = get_conan_user_home()
        assert str(os.path.join(_temp_folder, subfolder)) == conan_home


def test_conanrc_local_path_run_conan_subfolder_get_conan_user_home():
    _temp_folder = temp_folder(path_with_spaces=True)
    folder_conan_runs = os.path.join(_temp_folder, "folder_where_conan_runs")
    os.mkdir(folder_conan_runs)
    with open(os.path.join(_temp_folder, ".conanrc"), 'w+') as file:
        file.write(f'conan_home=.{os.sep}\n')
    with chdir(folder_conan_runs):
        conan_home = get_conan_user_home()
        assert str(os.path.join(_temp_folder)) == conan_home


def test_conanrc_local_outside_folder_path_get_conan_user_home():
    _temp_folder = temp_folder(path_with_spaces=True)
    folder1 = os.path.join(_temp_folder, "folder1")
    os.mkdir(folder1)
    with chdir(folder1):
        with open(os.path.join(folder1, ".conanrc"), 'w+') as file:
            file.write(f'conan_home=..{os.sep}folder2\n')
        conan_home = get_conan_user_home()
        this_path = Path(_temp_folder) / "folder1" / f"..{os.sep}folder2"
        assert str(this_path) == str(conan_home)


def test_conanrc_comments():
    _temp_folder = temp_folder(path_with_spaces=True)
    with chdir(_temp_folder):
        with open(os.path.join(_temp_folder, ".conanrc"), 'w+') as file:
            file.write(f'#commenting something\nconan_home={_temp_folder}\n')
        conan_home = get_conan_user_home()
        assert _temp_folder == conan_home


def test_conanrc_wrong_format():
    _temp_folder = temp_folder(path_with_spaces=True)
    with chdir(_temp_folder):
        with open(os.path.join(_temp_folder, ".conanrc"), 'w+') as file:
            file.write(f'ronan_jome={_temp_folder}\n')
        conan_home = get_conan_user_home()
        assert _temp_folder not in conan_home


def test_conanrc_not_existing():
    _temp_folder = temp_folder(path_with_spaces=True)
    with chdir(_temp_folder):
        conan_home = get_conan_user_home()
        assert _temp_folder not in conan_home
