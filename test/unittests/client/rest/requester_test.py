import os

from conan.api.conan_api import ConanAPI
from conan.internal.cache.home_paths import HomePaths
from conan.internal.util.files import save
from conan.test.utils.test_files import temp_folder


def test_requester_reinit():
    """ Ensure the reinitialization of the requester gets the new global configuration """
    tmp_folder = temp_folder()
    home_path = HomePaths(tmp_folder)
    save(os.path.join(home_path.profiles_path, "default"), "")
    conan_api = ConanAPI(tmp_folder)
    save(os.path.join(home_path.global_conf_path), "core.net.http:timeout=(10, 20)")
    conan_api.reinit()
    assert conan_api.remotes.requester._timeout == (10, 20)
