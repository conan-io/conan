import json

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_info_build_order():
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile(),
            "pkg/conanfile.py": GenConanfile().with_requires("dep/0.1"),
            "consumer/conanfile.txt": "[requires]\npkg/0.1"})
    c.run("export dep dep/0.1@")
    c.run("export pkg pkg/0.1@")
    c.run("info  consumer --build-order=bo.json --build=missing")
    bo_json = json.loads(c.load("bo.json"))

    result = [
        [{
            "id": 1,
            "ref": "dep/0.1#f3367e0e7d170aa12abccb175fee5f97",
            "package_id": "357add7d387f11a959f3ee7d4fc9c2487dbaa604",
            "options": [],
            "depends": []
        }],
        [{
            "id": 2,
            "ref": "pkg/0.1#447b56f0334b7e2a28aa86e218c8b3bd",
            "package_id": "486166899301ccd88a8b71715c97eeea5cc3ff2b",
            "options": [],
            "depends": [1]
        }]
    ]

    assert bo_json == result
