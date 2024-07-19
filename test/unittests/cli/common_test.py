import os
from unittest.mock import MagicMock

import pytest

from conan.api.conan_api import ConanAPI
from conan.internal.cache.home_paths import HomePaths
from conans.errors import ConanException
from conan.test.utils.test_files import temp_folder
from conans.util.files import save


@pytest.fixture()
def conan_api():
    tmp_folder = temp_folder()
    home_path = HomePaths(tmp_folder)
    save(os.path.join(home_path.profiles_path, "default"), "")
    return ConanAPI(tmp_folder)


@pytest.fixture()
def argparse_args():
    return MagicMock(
        profile_build=None,
        profile_host=None,
        profile_all=None,
        settings_build=None,
        settings_host=None,
        settings_all=None,
        options_build=None,
        options_host=None,
        options_all=None,
        conf_build=None,
        conf_host=None,
        conf_all=None,
    )


@pytest.mark.parametrize("conf_name", [
    "core.doesnotexist:never",
    "core:doesnotexist"
])
def test_core_confs_not_allowed_via_cli(conan_api, argparse_args, conf_name):
    argparse_args.conf_build = [conf_name]
    argparse_args.conf_host = [conf_name]

    with pytest.raises(ConanException) as exc:
        conan_api.profiles.get_profiles_from_args(argparse_args)
    assert "[conf] 'core.*' configurations are not allowed in profiles" in str(exc.value)
