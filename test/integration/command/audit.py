from mock import mock
from mock.mock import PropertyMock, patch, MagicMock

from conan.test.utils.tools import TestClient, GenConanfile



@patch("conan.api.conan_api.RemotesAPI.requester")
def test_mock_proxy_return(
    conanRequesterMock,
):
    return_status = MagicMock()
    return_status.status_code = 200
    return_status.json = MagicMock(return_value={
        "data": {
            "zlib": {
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
    })
    conanRequesterMock.post = MagicMock(return_value=return_status)

    tc = TestClient(light=True)
    tc.run("audit list zlib/1.2.11", assert_error=True)
    assert "Authentication required for the CVE provider: 'conancenter" in tc.out

    tc.run("audit provider auth --name=conancenter --token=valid_token")

    tc.run("audit list zlib/1.2.11")
    assert "zlib/1.2.11 1 vulnerability found" in tc.out
