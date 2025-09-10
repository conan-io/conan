import pytest
from unittest.mock import patch

from conan.api.input import UserInput


class TestUserInput:

    @patch("conan.api.input.UserInput.get_username", return_value="username")
    @patch("conan.api.input.UserInput.get_password", return_value="passwd")
    def test_request_login(self, m1, m2):
        user_input = UserInput(non_interactive=False)

        # Use mocked ones
        u, p = user_input.request_login(remote_name="lol")
        assert u == "username"
        assert p == "passwd"

        # Use from argument
        username = "it's me!"
        u, p = user_input.request_login(remote_name="lol", username=username)
        assert u == username
        assert p == "passwd"
