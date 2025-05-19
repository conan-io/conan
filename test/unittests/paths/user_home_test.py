import os
from pathlib import Path

from conan.internal.paths import get_conan_user_home, find_file_walk_up
from conan.test.utils.test_files import temp_folder
from conan.internal.util.files import chdir


class TestConanUserHome:
    def test_conanrc_abs_path_get_conan_user_home(self):
        _temp_folder = temp_folder(path_with_spaces=True)
        folder_conan_runs = os.path.join(_temp_folder, "folder_where_conan_runs")
        os.mkdir(folder_conan_runs)
        with open(os.path.join(_temp_folder, ".conanrc"), 'w+') as file:
            file.write(f'conan_home={_temp_folder}\n')
        with chdir(folder_conan_runs):
            conan_home = get_conan_user_home()
            assert _temp_folder == conan_home


    def test_conanrc_local_path_get_conan_user_home(self):
        _temp_folder = temp_folder(path_with_spaces=True)
        subfolder = "subfolder inside temp"
        with chdir(_temp_folder):
            with open(os.path.join(_temp_folder, ".conanrc"), 'w+') as file:
                file.write(f'conan_home=.{os.sep}{subfolder}\n')
            conan_home = get_conan_user_home()
            assert str(os.path.join(_temp_folder, subfolder)) == conan_home


    def test_conanrc_local_path_run_conan_subfolder_get_conan_user_home(self):
        _temp_folder = temp_folder(path_with_spaces=True)
        folder_conan_runs = os.path.join(_temp_folder, "folder_where_conan_runs")
        os.mkdir(folder_conan_runs)
        with open(os.path.join(_temp_folder, ".conanrc"), 'w+') as file:
            file.write(f'conan_home=.{os.sep}\n')
        with chdir(folder_conan_runs):
            conan_home = get_conan_user_home()
            assert str(os.path.join(_temp_folder)) == conan_home


    def test_conanrc_local_outside_folder_path_get_conan_user_home(self):
        _temp_folder = temp_folder(path_with_spaces=True)
        folder1 = os.path.join(_temp_folder, "folder1")
        os.mkdir(folder1)
        with chdir(folder1):
            with open(os.path.join(folder1, ".conanrc"), 'w+') as file:
                file.write(f'conan_home=..{os.sep}folder2\n')
            conan_home = get_conan_user_home()
            this_path = Path(_temp_folder) / "folder1" / f"..{os.sep}folder2"
            assert str(this_path) == str(conan_home)


    def test_conanrc_comments(self):
        _temp_folder = temp_folder(path_with_spaces=True)
        with chdir(_temp_folder):
            with open(os.path.join(_temp_folder, ".conanrc"), 'w+') as file:
                file.write(f'#commenting something\nconan_home={_temp_folder}\n')
            conan_home = get_conan_user_home()
            assert _temp_folder == conan_home


    def test_conanrc_wrong_format(self):
        _temp_folder = temp_folder(path_with_spaces=True)
        with chdir(_temp_folder):
            with open(os.path.join(_temp_folder, ".conanrc"), 'w+') as file:
                file.write(f'ronan_jome={_temp_folder}\n')
            conan_home = get_conan_user_home()
            assert _temp_folder not in conan_home


    def test_conanrc_not_existing(self):
        _temp_folder = temp_folder(path_with_spaces=True)
        with chdir(_temp_folder):
            conan_home = get_conan_user_home()
            assert _temp_folder not in conan_home


class TestFindWalkFileUp:
    def test_find_file_walk_up(self):
        _temp_folder = temp_folder(path_with_spaces=True)
        leaf = os.path.join(_temp_folder, "one", "two", "three")
        os.makedirs(leaf)
        file_name = "test.txt"
        file_path = os.path.join(leaf, file_name)
        with open(file_path, 'w+') as file:
            file.write("test")
        found_file = find_file_walk_up(leaf, file_name)
        assert str(found_file) == file_path

    def test_find_file_walk_up_no_file_end(self):
        _temp_folder = temp_folder(path_with_spaces=True)
        leaf = os.path.join(_temp_folder, "one", "two", "three")
        os.makedirs(leaf)
        file_name = "test.txt"
        file_path = os.path.join(_temp_folder, file_name)
        with open(file_path, 'w+') as file:
            file.write("test")
        # We stop searching in "one", so we don't find the file one level above
        found_file = find_file_walk_up(leaf, file_name, end=os.path.join(_temp_folder, "one"))
        assert found_file is None

    def test_find_file_walk_up_no_file_no_end(self):
        _temp_folder = temp_folder(path_with_spaces=True)
        leaf = os.path.join(_temp_folder, "one", "two", "three")
        os.makedirs(leaf)
        file_name = "test.txt"
        found_file = find_file_walk_up(leaf, file_name)
        assert found_file is None

    def test_find_file_walk_up_no_file_end_outside_leaf(self):
        _temp_folder = temp_folder(path_with_spaces=True)
        leaf = os.path.join(_temp_folder, "one", "two", "three")
        os.makedirs(leaf)
        file_name = "test.txt"
        _second_temp_folder = temp_folder(path_with_spaces=True)

        found_file = find_file_walk_up(leaf, file_name, end=_second_temp_folder)
        assert found_file is None
