import json

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_info_build_order():
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile(),
            "pkg/conanfile.py": GenConanfile().with_requires("dep/0.1"),
            "consumer/conanfile.txt": "[requires]\npkg/0.1"})
    c.run("export dep dep/0.1@")
    c.run("export pkg pkg/0.1@")
    c.run("graph build-order consumer --json=bo.json --build=missing")
    bo_json = json.loads(c.load("bo.json"))

    result = [
        [
            {
                "ref": "dep/0.1#f3367e0e7d170aa12abccb175fee5f97",
                "depends": [],
                "packages": [
                    {
                        "pref": "dep/0.1#f3367e0e7d170aa12abccb175fee5f97:357add7d387f11a959f3ee7d4fc9c2487dbaa604",
                        "context": "host",
                        "binary": "Build",
                        "options": []
                    }
                ]
            }
        ],
        [
            {
                "ref": "pkg/0.1#447b56f0334b7e2a28aa86e218c8b3bd",
                "depends": [
                    "dep/0.1#f3367e0e7d170aa12abccb175fee5f97"
                ],
                "packages": [
                    {
                        "pref": "pkg/0.1#447b56f0334b7e2a28aa86e218c8b3bd:486166899301ccd88a8b71715c97eeea5cc3ff2b",
                        "context": "host",
                        "binary": "Build",
                        "options": []
                    }
                ]
            }
        ]
    ]

    assert bo_json == result


def test_info_build_order_build_require():
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile(),
            "pkg/conanfile.py": GenConanfile().with_build_requires("dep/0.1"),
            "consumer/conanfile.txt": "[requires]\npkg/0.1"})
    c.run("export dep dep/0.1@")
    c.run("export pkg pkg/0.1@")
    c.run("graph build-order  consumer --json=bo.json --build=missing")
    bo_json = json.loads(c.load("bo.json"))
    result = [
        [
            {
                "ref": "dep/0.1#f3367e0e7d170aa12abccb175fee5f97",
                "depends": [],
                "packages": [
                    {
                        "pref": "dep/0.1#f3367e0e7d170aa12abccb175fee5f97:357add7d387f11a959f3ee7d4fc9c2487dbaa604",
                        "context": "build",
                        "binary": "Build",
                        "options": []
                    }
                ]
            }
        ],
        [
            {
                "ref": "pkg/0.1#1364f701b47130c7e38f04c5e5fab985",
                "depends": [
                    "dep/0.1#f3367e0e7d170aa12abccb175fee5f97"
                ],
                "packages": [
                    {
                        "pref": "pkg/0.1#1364f701b47130c7e38f04c5e5fab985:357add7d387f11a959f3ee7d4fc9c2487dbaa604",
                        "context": "host",
                        "binary": "Build",
                        "options": []
                    }
                ]
            }
        ]
    ]

    assert bo_json == result


def test_info_build_order_options():
    c = TestClient()
    c.save({"tool/conanfile.py": GenConanfile().with_option("myopt", [1, 2, 3]),
            "dep1/conanfile.py": GenConanfile().with_build_requires("tool/0.1").with_default_option(
                "tool:myopt", 1),
            "dep2/conanfile.py": GenConanfile().with_build_requires("tool/0.1").with_default_option(
                "tool:myopt", 2),
            "consumer/conanfile.txt": "[requires]\ndep1/0.1\ndep2/0.1"})
    c.run("export tool tool/0.1@")
    c.run("export dep1 dep1/0.1@")
    c.run("export dep2 dep2/0.1@")

    c.run("graph build-order  consumer --json=bo.json --build=missing")

    bo_json = json.loads(c.load("bo.json"))

    result = [
        [
            {
                "ref": "tool/0.1#b6299fc637530d547c7eaa047d1da91d",
                "depends": [],
                "packages": [
                    {
                        "pref": "tool/0.1#b6299fc637530d547c7eaa047d1da91d:3da64a6c9584c99ed46ddf3a929787da9075a475",
                        "context": "build",
                        "binary": "Build",
                        "options": [
                            [
                                "myopt",
                                "1"
                            ]
                        ]
                    },
                    {
                        "pref": "tool/0.1#b6299fc637530d547c7eaa047d1da91d:656515670a0b81a38777e89d7984090eadc9919d",
                        "context": "build",
                        "binary": "Build",
                        "options": [
                            [
                                "myopt",
                                "2"
                            ]
                        ]
                    }
                ]
            }
        ],
        [
            {
                "ref": "dep1/0.1#36716458443ac8c76bf2e905323b331c",
                "depends": [
                    "tool/0.1#b6299fc637530d547c7eaa047d1da91d"
                ],
                "packages": [
                    {
                        "pref": "dep1/0.1#36716458443ac8c76bf2e905323b331c:357add7d387f11a959f3ee7d4fc9c2487dbaa604",
                        "context": "host",
                        "binary": "Build",
                        "options": [
                            [
                                "tool:myopt",
                                "1"
                            ]
                        ]
                    }
                ]
            },
            {
                "ref": "dep2/0.1#d7154a7eee8e107438768c1542ca1b70",
                "depends": [
                    "tool/0.1#b6299fc637530d547c7eaa047d1da91d"
                ],
                "packages": [
                    {
                        "pref": "dep2/0.1#d7154a7eee8e107438768c1542ca1b70:357add7d387f11a959f3ee7d4fc9c2487dbaa604",
                        "context": "host",
                        "binary": "Build",
                        "options": [
                            [
                                "tool:myopt",
                                "2"
                            ]
                        ]
                    }
                ]
            }
        ]
    ]

    assert bo_json == result


def test_info_build_order_multi_product():
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile(),
            "pkg/conanfile.py": GenConanfile().with_requires("dep/0.1"),
            "consumer1/conanfile.txt": "[requires]\npkg/0.1",
            "consumer2/conanfile.txt": "[requires]\npkg/0.2"})
    c.run("export dep dep/0.1@")
    c.run("export pkg pkg/0.1@")
    c.run("export pkg pkg/0.2@")
    c.run("graph build-order consumer1 --json=bo1.json --build=missing")
    c.run("graph build-order consumer2 --json=bo2.json --build=missing")
    c.run("graph build-order-merge --file=bo1.json --file=bo2.json --json=bo3.json")

    bo_json = json.loads(c.load("bo3.json"))

    result = [
        [
            {
                "ref": "dep/0.1#f3367e0e7d170aa12abccb175fee5f97",
                "depends": [],
                "packages": [
                    {
                        "pref": "dep/0.1#f3367e0e7d170aa12abccb175fee5f97:357add7d387f11a959f3ee7d4fc9c2487dbaa604",
                        "context": "host",
                        "binary": "Build",
                        "options": []
                    }
                ]
            }
        ],
        [
            {
                "ref": "pkg/0.1#447b56f0334b7e2a28aa86e218c8b3bd",
                "depends": [
                    "dep/0.1#f3367e0e7d170aa12abccb175fee5f97"
                ],
                "packages": [
                    {
                        "pref": "pkg/0.1#447b56f0334b7e2a28aa86e218c8b3bd:486166899301ccd88a8b71715c97eeea5cc3ff2b",
                        "context": "host",
                        "binary": "Build",
                        "options": []
                    }
                ]
            },
            {
                "ref": "pkg/0.2#447b56f0334b7e2a28aa86e218c8b3bd",
                "depends": [
                    "dep/0.1#f3367e0e7d170aa12abccb175fee5f97"
                ],
                "packages": [
                    {
                        "pref": "pkg/0.2#447b56f0334b7e2a28aa86e218c8b3bd:486166899301ccd88a8b71715c97eeea5cc3ff2b",
                        "context": "host",
                        "binary": "Build",
                        "options": []
                    }
                ]
            }
        ]
    ]

    assert bo_json == result
