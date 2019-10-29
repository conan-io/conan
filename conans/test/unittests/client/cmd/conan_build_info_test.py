import os
import textwrap
import unittest

from conans.build_info.build_info import update_build_info
from conans.test.utils.test_files import temp_folder
from conans.tools import save


class BuildInfoTest(unittest.TestCase):
    buildinfo1 = textwrap.dedent("""
    {
        "version": "1.0.1",
        "name": "MyBuildName",
        "number": "42",
        "type": "GENERIC",
        "started": "2019-10-28T17:54:20.000Z",
        "buildAgent": {
            "name": "Conan Client",
            "version": "1.X"
        },
        "modules": [
            {
                "id": "PkgB/0.2@user/channel",
                "properties": {},
                "artifacts": [
                    {
                        "sha1": "aba8527a2c4fc142cf5262298824d3680ecb057f",
                        "md5": "aad124317706ef90df47686329be8e2b",
                        "name": "conan_sources.tgz"
                    }
                ],
                "dependencies": [
                    {
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "id": "PkgA/0.1@user/channel :: conan_sources.tgz"
                    }
                ]
            },
            {
                "id": "PkgB/0.2@user/channel:5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5",
                "properties": {
                    "settings.arch": "x86_64",
                    "settings.arch_build": "x86_64",
                    "settings.build_type": "Release",
                    "settings.compiler": "apple-clang",
                    "settings.compiler.libcxx": "libc++",
                    "settings.compiler.version": "11.0",
                    "settings.os": "Macos",
                    "settings.os_build": "Macos"
                },
                "artifacts": [
                    {
                        "sha1": "45f961804e3bcc5267a2f6d130b4dcc16e2379ee",
                        "md5": "d4f703971717722bd84c24eccf50b9fd",
                        "name": "conan_package.tgz"
                    }
                ],
                "dependencies": [
                    {
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "id": "PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conan_package.tgz"
                    }
                ]
            }
        ]
    }
    """)

    buildinfo2 = textwrap.dedent("""
    {
        "version": "1.0.1",
        "name": "MyBuildName",
        "number": "42",
        "type": "GENERIC",
        "started": "2019-10-28T17:56:27.000Z",
        "buildAgent": {
            "name": "Conan Client",
            "version": "1.X"
        },
        "modules": [
            {
                "id": "PkgB/0.2@user/channel",
                "properties": {},
                "artifacts": [
                    {
                        "sha1": "aba8527a2c4fc142cf5262298824d3680ecb057f",
                        "md5": "aad124317706ef90df47686329be8e2b",
                        "name": "conan_sources.tgz"
                    },
                    {
                        "sha1": "a058b1a9366a361d71ea5d67997009f7200de6e1",
                        "md5": "a73be4ec0c7301d2ea2dacc873df5483",
                        "name": "conanfile.py"
                    },
                    {
                        "sha1": "1966d28a96848cf02d410bbf93e3b9c02bb53e3e",
                        "md5": "f1434c4e0e30c86a9a71b344fa56d9c2",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": [
                    {
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "id": "PkgA/0.1@user/channel :: conan_sources.tgz"
                    },
                    {
                        "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                        "md5": "00dbccdd251aa5652df8886cf153d2d6",
                        "id": "PkgA/0.1@user/channel :: conanfile.py"
                    },
                    {
                        "sha1": "4b23ada0b5e45bb8a7bb3216055c0b04cd0ea765",
                        "md5": "b8a9f5ebd3c290632716aabeb00f8088",
                        "id": "PkgA/0.1@user/channel :: conanmanifest.txt"
                    }
                ]
            },
            {
                "id": "PkgB/0.2@user/channel:5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5",
                "properties": {
                    "settings.arch": "x86_64",
                    "settings.arch_build": "x86_64",
                    "settings.build_type": "Release",
                    "settings.compiler": "apple-clang",
                    "settings.compiler.libcxx": "libc++",
                    "settings.compiler.version": "11.0",
                    "settings.os": "Macos",
                    "settings.os_build": "Macos"
                },
                "artifacts": [
                    {
                        "sha1": "45f961804e3bcc5267a2f6d130b4dcc16e2379ee",
                        "md5": "d4f703971717722bd84c24eccf50b9fd",
                        "name": "conan_package.tgz"
                    },
                    {
                        "sha1": "13440816251fbf4144481b0892247704bbd075a2",
                        "md5": "1d2bf7c2ed96a7a8a5bb828cedb52331",
                        "name": "conaninfo.txt"
                    },
                    {
                        "sha1": "49367e4c0010658d65c7da619592421d2026e432",
                        "md5": "15a49fb1eca58493a72b850086c1480c",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": [
                    {
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "id": "PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conan_package.tgz"
                    },
                    {
                        "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                        "md5": "95adc888e92d1a888454fae2093c0862",
                        "id": "PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conaninfo.txt"
                    },
                    {
                        "sha1": "1cf1f70abfae1e7952a6b0508f322f984629502c",
                        "md5": "14e2ea3d514c4df1f69868afe2021cce",
                        "id": "PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conanmanifest.txt"
                    }
                ]
            },
            {
                "id": "PkgC/0.2@user/channel",
                "properties": {},
                "artifacts": [
                    {
                        "sha1": "410b7df1fd1483a5a7b4c47e67822fc1e3dd533b",
                        "md5": "461fbd5d7e66ce86b8e56fb2524970dc",
                        "name": "conan_sources.tgz"
                    },
                    {
                        "sha1": "88e08df12a3c6593334315e9fb05c405f00c386e",
                        "md5": "885578d69dd2c1c3ff4f98ec1db5d1e8",
                        "name": "conanfile.py"
                    },
                    {
                        "sha1": "2bbbacdeefa5c39f0e8ed4fc9222cff7236133c6",
                        "md5": "00b55bda7ab586f52b1fae67b05cab05",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": [
                    {
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "id": "PkgA/0.1@user/channel :: conan_sources.tgz"
                    },
                    {
                        "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                        "md5": "00dbccdd251aa5652df8886cf153d2d6",
                        "id": "PkgA/0.1@user/channel :: conanfile.py"
                    },
                    {
                        "sha1": "4b23ada0b5e45bb8a7bb3216055c0b04cd0ea765",
                        "md5": "b8a9f5ebd3c290632716aabeb00f8088",
                        "id": "PkgA/0.1@user/channel :: conanmanifest.txt"
                    },
                    {
                        "sha1": "aba8527a2c4fc142cf5262298824d3680ecb057f",
                        "md5": "aad124317706ef90df47686329be8e2b",
                        "id": "PkgB/0.2@user/channel :: conan_sources.tgz"
                    },
                    {
                        "sha1": "a058b1a9366a361d71ea5d67997009f7200de6e1",
                        "md5": "a73be4ec0c7301d2ea2dacc873df5483",
                        "id": "PkgB/0.2@user/channel :: conanfile.py"
                    },
                    {
                        "sha1": "1966d28a96848cf02d410bbf93e3b9c02bb53e3e",
                        "md5": "f1434c4e0e30c86a9a71b344fa56d9c2",
                        "id": "PkgB/0.2@user/channel :: conanmanifest.txt"
                    }
                ]
            },
            {
                "id": "PkgC/0.2@user/channel:28b790da5910e39b6108f60ced9746d9e45f9bd1",
                "properties": {
                    "settings.arch": "x86_64",
                    "settings.arch_build": "x86_64",
                    "settings.build_type": "Release",
                    "settings.compiler": "apple-clang",
                    "settings.compiler.libcxx": "libc++",
                    "settings.compiler.version": "11.0",
                    "settings.os": "Macos",
                    "settings.os_build": "Macos"
                },
                "artifacts": [
                    {
                        "sha1": "8848e27090a687a65092862cc1e658415d2f32c1",
                        "md5": "eec3cefe35d36578c154dd2c9c6fb833",
                        "name": "conan_package.tgz"
                    },
                    {
                        "sha1": "43f07cad77c74ca871d891e831f8965fb59c5a7a",
                        "md5": "9992ecfd6f71d5544e9ccbdca92909f9",
                        "name": "conaninfo.txt"
                    },
                    {
                        "sha1": "f43001691df229d8a06bd4758e1db16c056f0680",
                        "md5": "9bef093b22510250b97e8d4aaa7f2aeb",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": [
                    {
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "id": "PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conan_package.tgz"
                    },
                    {
                        "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                        "md5": "95adc888e92d1a888454fae2093c0862",
                        "id": "PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conaninfo.txt"
                    },
                    {
                        "sha1": "1cf1f70abfae1e7952a6b0508f322f984629502c",
                        "md5": "14e2ea3d514c4df1f69868afe2021cce",
                        "id": "PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conanmanifest.txt"
                    },
                    {
                        "sha1": "45f961804e3bcc5267a2f6d130b4dcc16e2379ee",
                        "md5": "d4f703971717722bd84c24eccf50b9fd",
                        "id": "PkgB/0.2@user/channel:5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5 :: conan_package.tgz"
                    },
                    {
                        "sha1": "13440816251fbf4144481b0892247704bbd075a2",
                        "md5": "1d2bf7c2ed96a7a8a5bb828cedb52331",
                        "id": "PkgB/0.2@user/channel:5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5 :: conaninfo.txt"
                    },
                    {
                        "sha1": "49367e4c0010658d65c7da619592421d2026e432",
                        "md5": "15a49fb1eca58493a72b850086c1480c",
                        "id": "PkgB/0.2@user/channel:5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5 :: conanmanifest.txt"
                    }
                ]
            }
        ]
    }
    """)

    result = """{
    "version": "1.0.1",
    "name": "MyBuildName",
    "number": "42",
    "type": "GENERIC",
    "started": "2019-10-28T17:54:20.000Z",
    "buildAgent": {
        "name": "Conan Client",
        "version": "1.X"
    },
    "modules": [
        {
            "id": "PkgB/0.2@user/channel",
            "properties": {},
            "artifacts": [
                {
                    "sha1": "aba8527a2c4fc142cf5262298824d3680ecb057f",
                    "md5": "aad124317706ef90df47686329be8e2b",
                    "name": "conan_sources.tgz"
                },
                {
                    "sha1": "a058b1a9366a361d71ea5d67997009f7200de6e1",
                    "md5": "a73be4ec0c7301d2ea2dacc873df5483",
                    "name": "conanfile.py"
                },
                {
                    "sha1": "1966d28a96848cf02d410bbf93e3b9c02bb53e3e",
                    "md5": "f1434c4e0e30c86a9a71b344fa56d9c2",
                    "name": "conanmanifest.txt"
                }
            ],
            "dependencies": [
                {
                    "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                    "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                    "id": "PkgA/0.1@user/channel :: conan_sources.tgz"
                },
                {
                    "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                    "md5": "00dbccdd251aa5652df8886cf153d2d6",
                    "id": "PkgA/0.1@user/channel :: conanfile.py"
                },
                {
                    "sha1": "4b23ada0b5e45bb8a7bb3216055c0b04cd0ea765",
                    "md5": "b8a9f5ebd3c290632716aabeb00f8088",
                    "id": "PkgA/0.1@user/channel :: conanmanifest.txt"
                }
            ]
        },
        {
            "id": "PkgB/0.2@user/channel:5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5",
            "properties": {
                "settings.arch": "x86_64",
                "settings.arch_build": "x86_64",
                "settings.build_type": "Release",
                "settings.compiler": "apple-clang",
                "settings.compiler.libcxx": "libc++",
                "settings.compiler.version": "11.0",
                "settings.os": "Macos",
                "settings.os_build": "Macos"
            },
            "artifacts": [
                {
                    "sha1": "45f961804e3bcc5267a2f6d130b4dcc16e2379ee",
                    "md5": "d4f703971717722bd84c24eccf50b9fd",
                    "name": "conan_package.tgz"
                },
                {
                    "sha1": "13440816251fbf4144481b0892247704bbd075a2",
                    "md5": "1d2bf7c2ed96a7a8a5bb828cedb52331",
                    "name": "conaninfo.txt"
                },
                {
                    "sha1": "49367e4c0010658d65c7da619592421d2026e432",
                    "md5": "15a49fb1eca58493a72b850086c1480c",
                    "name": "conanmanifest.txt"
                }
            ],
            "dependencies": [
                {
                    "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                    "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                    "id": "PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conan_package.tgz"
                },
                {
                    "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                    "md5": "95adc888e92d1a888454fae2093c0862",
                    "id": "PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conaninfo.txt"
                },
                {
                    "sha1": "1cf1f70abfae1e7952a6b0508f322f984629502c",
                    "md5": "14e2ea3d514c4df1f69868afe2021cce",
                    "id": "PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conanmanifest.txt"
                }
            ]
        },
        {
            "id": "PkgC/0.2@user/channel",
            "properties": {},
            "artifacts": [
                {
                    "sha1": "410b7df1fd1483a5a7b4c47e67822fc1e3dd533b",
                    "md5": "461fbd5d7e66ce86b8e56fb2524970dc",
                    "name": "conan_sources.tgz"
                },
                {
                    "sha1": "88e08df12a3c6593334315e9fb05c405f00c386e",
                    "md5": "885578d69dd2c1c3ff4f98ec1db5d1e8",
                    "name": "conanfile.py"
                },
                {
                    "sha1": "2bbbacdeefa5c39f0e8ed4fc9222cff7236133c6",
                    "md5": "00b55bda7ab586f52b1fae67b05cab05",
                    "name": "conanmanifest.txt"
                }
            ],
            "dependencies": [
                {
                    "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                    "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                    "id": "PkgA/0.1@user/channel :: conan_sources.tgz"
                },
                {
                    "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                    "md5": "00dbccdd251aa5652df8886cf153d2d6",
                    "id": "PkgA/0.1@user/channel :: conanfile.py"
                },
                {
                    "sha1": "4b23ada0b5e45bb8a7bb3216055c0b04cd0ea765",
                    "md5": "b8a9f5ebd3c290632716aabeb00f8088",
                    "id": "PkgA/0.1@user/channel :: conanmanifest.txt"
                },
                {
                    "sha1": "aba8527a2c4fc142cf5262298824d3680ecb057f",
                    "md5": "aad124317706ef90df47686329be8e2b",
                    "id": "PkgB/0.2@user/channel :: conan_sources.tgz"
                },
                {
                    "sha1": "a058b1a9366a361d71ea5d67997009f7200de6e1",
                    "md5": "a73be4ec0c7301d2ea2dacc873df5483",
                    "id": "PkgB/0.2@user/channel :: conanfile.py"
                },
                {
                    "sha1": "1966d28a96848cf02d410bbf93e3b9c02bb53e3e",
                    "md5": "f1434c4e0e30c86a9a71b344fa56d9c2",
                    "id": "PkgB/0.2@user/channel :: conanmanifest.txt"
                }
            ]
        },
        {
            "id": "PkgC/0.2@user/channel:28b790da5910e39b6108f60ced9746d9e45f9bd1",
            "properties": {
                "settings.arch": "x86_64",
                "settings.arch_build": "x86_64",
                "settings.build_type": "Release",
                "settings.compiler": "apple-clang",
                "settings.compiler.libcxx": "libc++",
                "settings.compiler.version": "11.0",
                "settings.os": "Macos",
                "settings.os_build": "Macos"
            },
            "artifacts": [
                {
                    "sha1": "8848e27090a687a65092862cc1e658415d2f32c1",
                    "md5": "eec3cefe35d36578c154dd2c9c6fb833",
                    "name": "conan_package.tgz"
                },
                {
                    "sha1": "43f07cad77c74ca871d891e831f8965fb59c5a7a",
                    "md5": "9992ecfd6f71d5544e9ccbdca92909f9",
                    "name": "conaninfo.txt"
                },
                {
                    "sha1": "f43001691df229d8a06bd4758e1db16c056f0680",
                    "md5": "9bef093b22510250b97e8d4aaa7f2aeb",
                    "name": "conanmanifest.txt"
                }
            ],
            "dependencies": [
                {
                    "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                    "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                    "id": "PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conan_package.tgz"
                },
                {
                    "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                    "md5": "95adc888e92d1a888454fae2093c0862",
                    "id": "PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conaninfo.txt"
                },
                {
                    "sha1": "1cf1f70abfae1e7952a6b0508f322f984629502c",
                    "md5": "14e2ea3d514c4df1f69868afe2021cce",
                    "id": "PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conanmanifest.txt"
                },
                {
                    "sha1": "45f961804e3bcc5267a2f6d130b4dcc16e2379ee",
                    "md5": "d4f703971717722bd84c24eccf50b9fd",
                    "id": "PkgB/0.2@user/channel:5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5 :: conan_package.tgz"
                },
                {
                    "sha1": "13440816251fbf4144481b0892247704bbd075a2",
                    "md5": "1d2bf7c2ed96a7a8a5bb828cedb52331",
                    "id": "PkgB/0.2@user/channel:5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5 :: conaninfo.txt"
                },
                {
                    "sha1": "49367e4c0010658d65c7da619592421d2026e432",
                    "md5": "15a49fb1eca58493a72b850086c1480c",
                    "id": "PkgB/0.2@user/channel:5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5 :: conanmanifest.txt"
                }
            ]
        }
    ]\n}"""

    def update_build_info_test(self):
        tmp_dir = temp_folder()
        file1 = os.path.join(tmp_dir, "buildinfo1.json")
        file2 = os.path.join(tmp_dir, "buildinfo2.json")
        outfile = os.path.join(tmp_dir, "mergedbuildinfo.json")
        save(file1, self.buildinfo1)
        save(file2, self.buildinfo2)
        update_build_info([file1, file2], outfile)
        with open(outfile, "r") as json_data:
            mergedinfo = json_data.read()
            self.assertEqual(mergedinfo, self.result)
