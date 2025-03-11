from contextlib import contextmanager

from mock.mock import patch, MagicMock

from conan.test.assets.genconanfile import GenConanfile
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
                "version": "1.2.11",
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
    assert "ERROR: Provider 'conancenter' not found" in tc.out
