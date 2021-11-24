import json
import textwrap

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
                        "package_id": "357add7d387f11a959f3ee7d4fc9c2487dbaa604",
                        'prev': None,
                        'filenames': [],
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
                        "package_id": "486166899301ccd88a8b71715c97eeea5cc3ff2b",
                        'prev': None,
                        'filenames': [],
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
            "pkg/conanfile.py": GenConanfile().with_build_tool_requires("dep/0.1"),
            "consumer/conanfile.txt": "[requires]\npkg/0.1"})
    c.run("export dep dep/0.1@")
    c.run("export pkg pkg/0.1@")
    c.run("graph build-order  consumer --json=bo.json --build=missing")
    bo_json = json.loads(c.load("bo.json"))
    result = [
        [
            {
                "ref": 'dep/0.1#f3367e0e7d170aa12abccb175fee5f97',
                "depends": [],
                "packages": [
                    {
                        "package_id": "357add7d387f11a959f3ee7d4fc9c2487dbaa604",
                        'prev': None,
                        'filenames': [],
                        "context": "build",
                        "binary": "Build",
                        "options": []
                    }
                ]
            }
        ],
        [
            {
                "ref": "pkg/0.1#7a8e9776f7216a0fabaf97d28a1cca9b",
                "depends": [
                    "dep/0.1#f3367e0e7d170aa12abccb175fee5f97"
                ],
                "packages": [
                    {
                        "package_id": "357add7d387f11a959f3ee7d4fc9c2487dbaa604",
                        'prev': None,
                        'filenames': [],
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
            "dep1/conanfile.py": GenConanfile().with_build_tool_requires("tool/0.1").
           with_default_option("tool:myopt", 1),
            "dep2/conanfile.py": GenConanfile().with_build_tool_requires("tool/0.1").
           with_default_option("tool:myopt", 2),
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
                        "package_id": "3da64a6c9584c99ed46ddf3a929787da9075a475",
                        'prev': None,
                        'filenames': [],
                        "context": "build",
                        "binary": "Build",
                        "options": [
                                "tool:myopt=1"
                        ]
                    },
                    {
                        "package_id": "656515670a0b81a38777e89d7984090eadc9919d",
                        'prev': None,
                        'filenames': [],
                        "context": "build",
                        "binary": "Build",
                        "options": [
                                "tool:myopt=2"
                        ]
                    }
                ]
            }
        ],
        [
            {
                "ref": "dep1/0.1#4f93589729d403a79c72107096995dc3",
                "depends": [
                    "tool/0.1#b6299fc637530d547c7eaa047d1da91d"
                ],
                "packages": [
                    {
                        "package_id": "357add7d387f11a959f3ee7d4fc9c2487dbaa604",
                        'prev': None,
                        'filenames': [],
                        "context": "host",
                        "binary": "Build",
                        "options": [
                        ]
                    }
                ]
            },
            {
                "ref": "dep2/0.1#e850501253070d94d558a7b72fdd578c",
                "depends": [
                    "tool/0.1#b6299fc637530d547c7eaa047d1da91d"
                ],
                "packages": [
                    {
                        "package_id": "357add7d387f11a959f3ee7d4fc9c2487dbaa604",
                        'prev': None,
                        'filenames': [],
                        "context": "host",
                        "binary": "Build",
                        "options": [
                        ]
                    }
                ]
            }
        ]
    ]

    assert bo_json == result


def test_info_build_order_merge_multi_product():
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
                        "package_id": "357add7d387f11a959f3ee7d4fc9c2487dbaa604",
                        'prev': None,
                        'filenames': ["bo1", "bo2"],
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
                        "package_id": "486166899301ccd88a8b71715c97eeea5cc3ff2b",
                        'prev': None,
                        'filenames': ["bo1"],
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
                        "package_id": "486166899301ccd88a8b71715c97eeea5cc3ff2b",
                        'prev': None,
                        'filenames': ["bo2"],
                        "context": "host",
                        "binary": "Build",
                        "options": []
                    }
                ]
            }
        ]
    ]

    assert bo_json == result


def test_info_build_order_merge_conditionals():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            def requirements(self):
                if self.settings.os == "Windows":
                    self.requires("depwin/[>0.0 <1.0]")
                else:
                    self.requires("depnix/[>0.0 <1.0]")
        """)
    c.save({"dep/conanfile.py": GenConanfile(),
            "pkg/conanfile.py": conanfile,
            "consumer/conanfile.txt": "[requires]\npkg/0.1"})
    c.run("export dep depwin/0.1@")
    c.run("export dep depnix/0.1@")
    c.run("export pkg pkg/0.1@")
    c.run("graph build-order consumer --json=bo_win.json --build=missing -s os=Windows")
    c.run("graph build-order consumer --json=bo_nix.json --build=missing -s os=Linux")
    c.run("graph build-order-merge --file=bo_win.json --file=bo_nix.json --json=bo3.json")

    bo_json = json.loads(c.load("bo3.json"))

    result = [
        [
            {
                "ref": "depwin/0.1#f3367e0e7d170aa12abccb175fee5f97",
                "depends": [],
                "packages": [
                    {
                        "package_id": "357add7d387f11a959f3ee7d4fc9c2487dbaa604",
                        'prev': None,
                        'filenames': ["bo_win"],
                        "context": "host",
                        "binary": "Build",
                        "options": []
                    }
                ]
            },
            {
                "ref": "depnix/0.1#f3367e0e7d170aa12abccb175fee5f97",
                "depends": [],
                "packages": [
                    {
                        "package_id": "357add7d387f11a959f3ee7d4fc9c2487dbaa604",
                        'prev': None,
                        'filenames': ["bo_nix"],
                        "context": "host",
                        "binary": "Build",
                        "options": []
                    }
                ]
            }
        ],
        [
            {
                "ref": "pkg/0.1#df708aff3c643ce78d6ea456cab80671",
                "depends": [
                    "depwin/0.1#f3367e0e7d170aa12abccb175fee5f97",
                    "depnix/0.1#f3367e0e7d170aa12abccb175fee5f97"
                ],
                "packages": [
                    {
                        "package_id": "fe0818ee6bf52c8906f551e114ea476081219a57",
                        'prev': None,
                        'filenames': ["bo_win"],
                        "context": "host",
                        "binary": "Build",
                        "options": []
                    },
                    {
                        "package_id": "089e881a859748afac9c03e5badf9163f62a6cf9",
                        'prev': None,
                        'filenames': ["bo_nix"],
                        "context": "host",
                        "binary": "Build",
                        "options": []
                    }
                ]
            }
        ]
    ]

    assert bo_json == result
