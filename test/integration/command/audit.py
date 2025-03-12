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
                                    "preferredBaseScore": 9.8
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
        tc.run("audit list zlib/1.2.11")
        assert "You have exceeded the number of allowed requests" in tc.out
        assert "The limit will reset in 1 minute" in tc.out

    with proxy_response(400, {"error": "Not found"}):
        tc.run("audit list zlib/1.2.11")
        assert "Package 'zlib/1.2.11' not found" in tc.out

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


@pytest.mark.skipif(sys.version_info < (3, 10),
                    reason="Strict Base64 validation introduced in Python 3.10")
def test_conan_audit_corrupted_token():
    tc = TestClient(light=True)
    tc.run('audit provider auth --name=conancenter --token="corrupted_token"')
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

    def fake_post(url, headers, json):
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
