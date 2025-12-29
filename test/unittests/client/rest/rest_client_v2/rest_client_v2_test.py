from conan.internal.rest.rest_client_v2 import RestV2Methods
from unittest.mock import MagicMock, patch


@patch("conan.internal.rest.conan_requester.ConanRequester")
def test_check_credentials_set_token_to_unset_with_force_auth_true_and_token_none(requester_mock):
    return_status = MagicMock()
    return_status.status_code = 200
    requester_mock.get = MagicMock(return_value=return_status)

    rest_v2_methods = RestV2Methods("foo", None, requester_mock, None, True)
    rest_v2_methods.check_credentials(True)

    assert requester_mock.get.call_args[1]["auth"].bearer == "Bearer unset"


@patch("conan.internal.rest.conan_requester.ConanRequester")
def test_check_credentials_keep_token_none_with_force_auth_false_and_token_none(requester_mock):
    return_status = MagicMock()
    return_status.status_code = 200
    requester_mock.get = MagicMock(return_value=return_status)

    rest_v2_methods = RestV2Methods("foo", None, requester_mock, None, True)
    rest_v2_methods.check_credentials(False)

    assert requester_mock.get.call_args[1]["auth"].bearer is None
