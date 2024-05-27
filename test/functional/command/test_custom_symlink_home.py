import os
import platform

import pytest

from conan.test.utils.scm import create_local_git_repo
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conans.util.files import save


@pytest.mark.skipif(platform.system() == "Windows", reason="Uses symlinks")
def test_custom_symlinked_home_config_install():
    base_cache = temp_folder()
    real_cache = os.path.join(base_cache, "real_cache")
    os.makedirs(real_cache)
    symlink_cache = os.path.join(base_cache, "symlink_cache")
    os.symlink(real_cache, symlink_cache)
    origin_folder = temp_folder()
    save(os.path.join(origin_folder, "myfile.txt"), "some contents")
    create_local_git_repo(folder=origin_folder)
    c = TestClient(cache_folder=symlink_cache)
    c.run(f'config install "{origin_folder}" --type=git')
    assert "Copying file myfile.txt to" in c.out
