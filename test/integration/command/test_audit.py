import json
import os
import platform
import sys
from contextlib import contextmanager

import pytest
from mock.mock import patch, MagicMock

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.env import environment_update
from conan.test.utils.tools import TestClient


@contextmanager
def proxy_response(status, data):
    with patch("conan.api.conan_api.RemotesAPI.requester") as conanRequesterMock:
        return_status = MagicMock()
        return_status.status_code = status
        return_status.json = MagicMock(return_value=data)
        return_status.headers = {"retry-after": 60}
        conanRequesterMock.post = MagicMock(return_value=return_status)

        yield conanRequesterMock, return_status


def test_conan_audit_paths():
    successful_response = {
        "data": {
            "query": {
                "vulnerabilities": {
                    "totalCount": 1,
                    "edges": [
                        {
                            "node": {
                                "name": "CVE-2023-45853",
                                "description": "Zip vulnerability",
                                "severity": "Critical",
                                "cvss": {
                                    "preferredBaseScore": 8.9
                                },
                                "aliases": [
                                    "CVE-2023-45853",
                                    "JFSA-2023-000272529"
                                ],
                                "advisories": [
                                    {
                                        "name": "CVE-2023-45853"
                                    },
                                    {
                                        "name": "JFSA-2023-000272529"
                                    }
                                ],
                                "references": [
                                    "https://pypi.org/project/pyminizip/#history",
                                ]
                            }
                        }
                    ]
                }
            }
        },
        "error": None
    }

    tc = TestClient(light=True)

    tc.save({"conanfile.py": GenConanfile("zlib", "1.2.11")})
    tc.run("export .")

    tc.run("list '*' -f=json", redirect_stdout="pkglist.json")

    tc.run("audit list zlib/1.2.11", assert_error=True)
    assert "Authentication required for the CVE provider: 'conancenter" in tc.out

    tc.run("audit provider auth conancenter --token=valid_token")

    with proxy_response(200, successful_response):
        tc.run("audit list zlib/1.2.11")
        assert "zlib/1.2.11 1 vulnerability found" in tc.out

        tc.run("audit list -l=pkglist.json")
        assert "zlib/1.2.11 1 vulnerability found" in tc.out

        tc.run("audit scan --requires=zlib/1.2.11")
        assert "zlib/1.2.11 1 vulnerability found" in tc.out

    # Now some common errors, like rate limited or missing lib, but it should not fail!
    with proxy_response(429, {"error": "Rate limit exceeded"}):
        tc.run("audit list zlib/1.2.11", assert_error=True)
        assert "You have exceeded the number of allowed requests" in tc.out
        assert "The limit will reset in 1 minute" in tc.out

    with proxy_response(400, {"error": "Not found"}):
        tc.run("audit list zlib/1.2.11")
        assert "Package 'zlib/1.2.11' not scanned: Not found." in tc.stdout

    tc.run("audit provider add myprivate --url=foo --type=private --token=valid_token")

    tc.run("audit provider list")
    assert "(type: conan-center-proxy)" in tc.out
    assert "(type: private)" in tc.out

    tc.run("audit provider remove conancenter")
    tc.run("audit list zlib/1.2.11", assert_error=True)
    assert ("ERROR: Provider 'conancenter' not found. Please specify a valid provider name or add "
            "it using: 'conan audit provider add conancenter --url=https://audit.conan.io/ "
            "--type=conan-center-proxy --token=<token>'") in tc.out
    assert "If you don't have a valid token, register at: https://audit.conan.io/register." in tc.out

    if platform.system() != "Windows":
        providers_stat = os.stat(os.path.join(tc.cache_folder, "audit_providers.json"))
        # Assert that only the current user can read/write the file
        assert providers_stat.st_uid == os.getuid()
        assert providers_stat.st_gid == os.getgid()
        assert providers_stat.st_mode & 0o777 == 0o600


@pytest.mark.skipif(sys.version_info < (3, 10),
                    reason="Strict Base64 validation introduced in Python 3.10")
def test_conan_audit_corrupted_token():
    tc = TestClient(light=True)

    json_path = os.path.join(tc.cache_folder, "audit_providers.json")
    with open(json_path, "r") as f:
        data = json.load(f)

    # this is not a valid base64 string and will raise an exception
    data["conancenter"]["token"] = "corrupted_token"

    with open(json_path, "w") as f:
        json.dump(data, f)
    tc.run("audit list zlib/1.2.11", assert_error=True)
    assert "Invalid token format for provider 'conancenter'. The token might be corrupt." in tc.out


def test_audit_list_conflicting_args():
    tc = TestClient(light=True)
    tc.save({"pkglist.json": '{"Local Cache": {"zlib/1.2.11": {}}}'})
    tc.run("audit list zlib/1.2.11 -l=pkglist.json", assert_error=True)
    assert "Please specify a reference or a pkglist file, not both" in tc.out


def test_audit_provider_add_missing_url():
    tc = TestClient(light=True)
    tc.run("audit provider add myprivate --type=private --token=valid_token", assert_error=True)
    assert "Name, URL and type are required to add a provider" in tc.out


def test_audit_provider_remove_nonexistent():
    tc = TestClient(light=True)
    tc.run("audit provider remove nonexistingprovider", assert_error=True)
    assert "Provider 'nonexistingprovider' not found" in tc.out


def test_audit_list_missing_arguments():
    tc = TestClient(light=True)
    tc.run("audit list", assert_error=True)
    assert "Please specify a reference or a pkglist file" in tc.out


def test_audit_provider_env_credentials_with_proxy(monkeypatch):
    tc = TestClient(light=True)
    # Authenticate the provider with an old token to verify that the env variable overrides it
    tc.run("audit provider auth conancenter --token=old_token")

    captured_headers = {}

    def fake_post(url, headers, json):  # noqa
        # Capture the headers used in the request
        captured_headers.update(headers)
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "data": {"query": {"vulnerabilities": {"totalCount": 0, "edges": []}}}
        }
        response.headers = {"retry-after": 60}
        return response

    with environment_update({"CONAN_AUDIT_PROVIDER_TOKEN_CONANCENTER": "env_token_value"}):
        with patch("conan.api.conan_api.RemotesAPI.requester",
                   new_callable=MagicMock) as requester_mock:
            requester_mock.post = fake_post
            tc.run("audit list zlib/1.2.11")

    # Verify that the Authorization header uses the token from the environment variable
    assert captured_headers.get("Authorization") == "Bearer env_token_value"


def test_audit_global_error_exception():
    """
    Test that a global error returned by the provider results in ConanException
    raised by the formatter, using the 'details' field.
    """
    tc = TestClient(light=True)
    tc.run("audit provider auth conancenter --token=valid_token")

    mock_provider_result = {
        "data": {},
        "conan_error": "Fatal error."
    }

    with patch("conan.api.conan_api.AuditAPI.list", return_value=mock_provider_result):
        tc.run("audit list zlib/1.2.11", assert_error=True)
        assert "ERROR: Fatal error." in tc.out

        tc.run("audit list zlib/1.2.11 -f json", assert_error=True)
        assert "ERROR: Fatal error." in tc.out

        tc.run("audit list zlib/1.2.11 -f html", assert_error=True)
        assert "ERROR: Fatal error." in tc.out


@pytest.mark.parametrize("severity_level, threshold, should_fail", [
    (1.0, None, False),
    (8.9, None, False),
    (9.0, None, True),
    (9.1, None, True),
    (5.0, 5.1, False),
    (5.1, 5.1, True),
    (5.2, 5.1, True),
    (9.0, 11.0, False),
])
def test_audit_scan_threshold_error(severity_level, threshold, should_fail):
    """In case the severity level is equal or higher than the found for a CVE,
       the command should output the information as usual, and exit with non-success code error.
    """
    successful_response = {
        "data": {
            "query": {
                "vulnerabilities": {
                    "totalCount": 1,
                    "edges": [
                        {
                            "node": {
                                "name": "CVE-2023-45853",
                                "description": "Zip vulnerability",
                                "severity": "Critical",
                                "cvss": {
                                    "preferredBaseScore": severity_level
                                },
                                "aliases": [
                                    "CVE-2023-45853",
                                    "JFSA-2023-000272529"
                                ],
                                "advisories": [
                                    {
                                        "name": "CVE-2023-45853"
                                    },
                                    {
                                        "name": "JFSA-2023-000272529"
                                    }
                                ],
                                "references": [
                                    "https://pypi.org/project/pyminizip/#history",
                                ]
                            }
                        }
                    ]
                }
            }
        }
    }

    tc = TestClient(light=True)

    tc.save({"conanfile.py": GenConanfile("foobar", "0.1.0")})
    tc.run("export .")
    tc.run("audit provider auth conancenter --token=valid_token")

    with proxy_response(200, successful_response):
        severity_param = "" if threshold is None else f"-sl {threshold}"
        tc.run(f"audit scan --requires=foobar/0.1.0 {severity_param}", assert_error=should_fail)
        assert "foobar/0.1.0 1 vulnerability found" in tc.out
        assert f"CVSS: {severity_level}" in tc.out
        if should_fail:
            if threshold is None:
                threshold = "9.0"
            assert f"ERROR: The package foobar/0.1.0 has a CVSS score {severity_level} and exceeded the threshold severity level {threshold}" in tc.out
