import pytest

from conan.api.conan_api import ConanAPI
from conan.errors import ConanException


def test_profile_api():
    # It must be an absolute path
    with pytest.raises(ConanException) as e:
        ConanAPI(cache_folder="test")
    assert "cache_folder has to be an absolute path" in str(e.value)
