import json
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_info_build_order():
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile(),
            "pkg/conanfile.py": GenConanfile().with_requires("dep/0.1"),
            "consumer/conanfile.txt": "[requires]\npkg/0.1"})
    c.run("export dep --name=dep --version=0.1")
    c.run("export pkg --name=pkg --version=0.1")
    c.run("graph build-order consumer --build=missing --format=json")
    bo_json = json.loads(c.stdout)

    result = [
        [
            {
                "ref": "dep/0.1#4d670581ccb765839f2239cc8dff8fbd",
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
                "ref": "pkg/0.1#1ac8dd17c0f9f420935abd3b6a8fa032",
                "depends": [
                    "dep/0.1#4d670581ccb765839f2239cc8dff8fbd"
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
            "pkg/conanfile.py": GenConanfile().with_tool_requires("dep/0.1"),
            "consumer/conanfile.txt": "[requires]\npkg/0.1"})
    c.run("export dep --name=dep --version=0.1")
    c.run("export pkg --name=pkg --version=0.1")
    c.run("graph build-order  consumer --build=missing --format=json")
    bo_json = json.loads(c.stdout)
    result = [
        [
            {
                "ref": 'dep/0.1#4d670581ccb765839f2239cc8dff8fbd',
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
                "ref": "pkg/0.1#b5a40d7314ce57ebdcf8fa31257f3de1",
                "depends": [
                    "dep/0.1#4d670581ccb765839f2239cc8dff8fbd"
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
    # The normal default_options do NOT propagate to build_requires, it is necessary to use
    # self.requires(..., options=xxx)
    c.save({"tool/conanfile.py": GenConanfile().with_option("myopt", [1, 2, 3]),
            "dep1/conanfile.py": GenConanfile().with_tool_requirement("tool/0.1",
                                                                      options={"myopt": 1}),
            "dep2/conanfile.py": GenConanfile().with_tool_requirement("tool/0.1",
                                                                      options={"myopt": 2}),
            "consumer/conanfile.txt": "[requires]\ndep1/0.1\ndep2/0.1"})
    c.run("export tool --name=tool --version=0.1")
    c.run("export dep1 --name=dep1 --version=0.1")
    c.run("export dep2 --name=dep2 --version=0.1")

    c.run("graph build-order  consumer --build=missing --format=json")
    bo_json = json.loads(c.stdout)

    result = [
        [
            {
                "ref": "tool/0.1#b4c19a1357b43877a2019dd2804336a9",
                "depends": [],
                "packages": [
                    {
                        "package_id": "3da64a6c9584c99ed46ddf3a929787da9075a475",
                        'prev': None,
                        'filenames': [],
                        "context": "build",
                        "binary": "Build",
                        "options": [
                                "tool/0.1#b4c19a1357b43877a2019dd2804336a9:myopt=1"
                        ]
                    },
                    {
                        "package_id": "656515670a0b81a38777e89d7984090eadc9919d",
                        'prev': None,
                        'filenames': [],
                        "context": "build",
                        "binary": "Build",
                        "options": [
                                "tool/0.1#b4c19a1357b43877a2019dd2804336a9:myopt=2"
                        ]
                    }
                ]
            }
        ],
        [
            {
                "ref": "dep1/0.1#7f0d80f9cb8c6bab06def7f6fb8f3b86",
                "depends": [
                    "tool/0.1#b4c19a1357b43877a2019dd2804336a9"
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
                "ref": "dep2/0.1#23c789d2b36f0461e52cd6f139f97f5e",
                "depends": [
                    "tool/0.1#b4c19a1357b43877a2019dd2804336a9"
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
    c.run("export dep --name=dep --version=0.1")
    c.run("export pkg --name=pkg --version=0.1")
    c.run("export pkg --name=pkg --version=0.2")
    c.run("graph build-order consumer1  --build=missing --format=json", redirect_stdout="bo1.json")
    c.run("graph build-order consumer2  --build=missing --format=json", redirect_stdout="bo2.json")
    c.run("graph build-order-merge --file=bo1.json --file=bo2.json --format=json",
          redirect_stdout="bo3.json")

    bo_json = json.loads(c.load("bo3.json"))

    result = [
        [
            {
                "ref": "dep/0.1#4d670581ccb765839f2239cc8dff8fbd",
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
                "ref": "pkg/0.1#1ac8dd17c0f9f420935abd3b6a8fa032",
                "depends": [
                    "dep/0.1#4d670581ccb765839f2239cc8dff8fbd"
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
                "ref": "pkg/0.2#1ac8dd17c0f9f420935abd3b6a8fa032",
                "depends": [
                    "dep/0.1#4d670581ccb765839f2239cc8dff8fbd"
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
        from conan import ConanFile
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
    c.run("export dep --name=depwin --version=0.1")
    c.run("export dep --name=depnix --version=0.1")
    c.run("export pkg --name=pkg --version=0.1")
    c.run("graph build-order consumer --format=json --build=missing -s os=Windows",
          redirect_stdout="bo_win.json")
    c.run("graph build-order consumer --format=json --build=missing -s os=Linux",
          redirect_stdout="bo_nix.json")
    c.run("graph build-order-merge --file=bo_win.json --file=bo_nix.json --format=json",
          redirect_stdout="bo3.json")

    bo_json = json.loads(c.load("bo3.json"))

    result = [
        [
            {
                "ref": "depwin/0.1#4d670581ccb765839f2239cc8dff8fbd",
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
                "ref": "depnix/0.1#4d670581ccb765839f2239cc8dff8fbd",
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
                "ref": "pkg/0.1#b615ac4c7cd16631cd9e924b68596fce",
                "depends": [
                    "depwin/0.1#4d670581ccb765839f2239cc8dff8fbd",
                    "depnix/0.1#4d670581ccb765839f2239cc8dff8fbd"
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
