import pytest

from conan.api.conan_api import ConanAPI
from conan.test.utils.test_files import temp_folder


@pytest.mark.parametrize("reinit", [True, False])
def test_subapis_dont_hold_helpers(reinit):
    """
    Ensure that sub-APIs of ConanAPI do not hold references to the helpers,
    as reinitialization of ConanAPI will create new helpers and the old ones
    will become stale.
    Any safe exceptions should be coded here, not dynamically in the API
    to avoid overhead.
    """
    cache_folder = temp_folder()
    conan_api = ConanAPI(cache_folder=cache_folder)
    helpers = [getattr(conan_api._api_helpers, d) for d in dir(conan_api._api_helpers)
               if not d.startswith("_") and not d.endswith("API")]
    if reinit:
        conan_api.reinit()
    for subapi in dir(conan_api):
        subattr = getattr(conan_api, subapi)
        if (type(subattr).__name__.endswith("API")
            # No workspace because accessing its attributes throws an exception
            # as it dynamically checks for workspace files
            and subapi != "workspace"):
            for d in dir(subattr):
                subapi_attr_d = getattr(subattr, d)
                assert not any(subapi_attr_d is h for h in helpers), \
                    (f"SubAPI {subapi} should not hold helpers from _api_helpers: "
                     f"but found '{d}' which is {subapi_attr_d}")
