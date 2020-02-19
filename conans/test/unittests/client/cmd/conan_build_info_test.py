import json
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
        "started": "2019-10-29T10:41:25.000Z",
        "buildAgent": {
            "name": "Conan Client",
            "version": "1.X"
        },
        "modules": [
            {
                "id": "PkgB/0.1@user/channel",
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
                        "sha1": "6cbda4a7286d9bb37eb3a6c97b150ed4939f4095",
                        "md5": "67abd07526f4abdf24f88f443c907f78",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": [
                    {
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "id": "PkgA/0.2@user/channel :: conan_sources.tgz"
                    },
                    {
                        "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                        "md5": "00dbccdd251aa5652df8886cf153d2d6",
                        "id": "PkgA/0.2@user/channel :: conanfile.py"
                    },
                    {
                        "sha1": "7ca1713befc9eabcfaaa244133e3e173307705f4",
                        "md5": "d723dfc35eb5a121e401818fdb43b210",
                        "id": "PkgA/0.2@user/channel :: conanmanifest.txt"
                    }
                ]
            },
            {
                "id": "PkgB/0.1@user/channel:09f152eb7b3e0a6e15a2a3f464245864ae8f8644",
                "artifacts": [
                    {
                        "sha1": "45f961804e3bcc5267a2f6d130b4dcc16e2379ee",
                        "md5": "d4f703971717722bd84c24eccf50b9fd",
                        "name": "conan_package.tgz"
                    },
                    {
                        "sha1": "9525339890e3b484d5e7d8f351957b6c2a28147f",
                        "md5": "fd6b4a992aa1254fa5a404888ed8c7ce",
                        "name": "conaninfo.txt"
                    },
                    {
                        "sha1": "f8f2795005c8fbfbcddae7224888d66a8f47f533",
                        "md5": "c18ffa171f4df3ab4af24dc443320a5a",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": [
                    {
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "id": "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conan_package.tgz"
                    },
                    {
                        "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                        "md5": "95adc888e92d1a888454fae2093c0862",
                        "id": "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conaninfo.txt"
                    },
                    {
                        "sha1": "fe0b6d9343648ae2b60d5c6c4ce765291cc278fb",
                        "md5": "2702b1656a7318c01112b90cca875867",
                        "id": "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conanmanifest.txt"
                    }
                ]
            },
            {
                "id": "PkgA/0.2@user/channel",
                "artifacts": [
                    {
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "name": "conan_sources.tgz"
                    },
                    {
                        "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                        "md5": "00dbccdd251aa5652df8886cf153d2d6",
                        "name": "conanfile.py"
                    },
                    {
                        "sha1": "7ca1713befc9eabcfaaa244133e3e173307705f4",
                        "md5": "d723dfc35eb5a121e401818fdb43b210",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": []
            },
            {
                "id": "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                "artifacts": [
                    {
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "name": "conan_package.tgz"
                    },
                    {
                        "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                        "md5": "95adc888e92d1a888454fae2093c0862",
                        "name": "conaninfo.txt"
                    },
                    {
                        "sha1": "fe0b6d9343648ae2b60d5c6c4ce765291cc278fb",
                        "md5": "2702b1656a7318c01112b90cca875867",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": []
            }
        ]
    }""")

    buildinfo2 = textwrap.dedent("""
    {
        "version": "1.0.1",
        "name": "MyBuildName",
        "number": "42",
        "type": "GENERIC",
        "started": "2019-10-29T10:41:25.000Z",
        "buildAgent": {
            "name": "Conan Client",
            "version": "1.X"
        },
        "modules": [
            {
                "id": "PkgC/0.1@user/channel",
                "artifacts": [
                    {
                        "sha1": "410b7df1fd1483a5a7b4c47e67822fc1e3dd533b",
                        "md5": "461fbd5d7e66ce86b8e56fb2524970dc",
                        "name": "conan_sources.tgz"
                    },
                    {
                        "sha1": "a058b1a9366a361d71ea5d67997009f7200de6e1",
                        "md5": "a73be4ec0c7301d2ea2dacc873df5483",
                        "name": "conanfile.py"
                    },
                    {
                        "sha1": "594ff68dadb4cbeb36ff724286032698098b41e7",
                        "md5": "19052f117ce1513c3a815f41fd704c24",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": [
                    {
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "id": "PkgA/0.2@user/channel :: conan_sources.tgz"
                    },
                    {
                        "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                        "md5": "00dbccdd251aa5652df8886cf153d2d6",
                        "id": "PkgA/0.2@user/channel :: conanfile.py"
                    },
                    {
                        "sha1": "7ca1713befc9eabcfaaa244133e3e173307705f4",
                        "md5": "d723dfc35eb5a121e401818fdb43b210",
                        "id": "PkgA/0.2@user/channel :: conanmanifest.txt"
                    }
                ]
            },
            {
                "id": "PkgC/0.1@user/channel:09f152eb7b3e0a6e15a2a3f464245864ae8f8644",
                "artifacts": [
                    {
                        "sha1": "0b6a6755369820f66d6a858d3b44775fb1b38f54",
                        "md5": "c1f3a9ff4ee80ab5e5492c1c381dff56",
                        "name": "conan_package.tgz"
                    },
                    {
                        "sha1": "6bce988c0cfc1d17588c0fddac573066afd8d26d",
                        "md5": "bde279efd0a24162425017d937fe8484",
                        "name": "conaninfo.txt"
                    },
                    {
                        "sha1": "6a85f6893f316433cd935abad31c4daf80d09884",
                        "md5": "5996a968f13f4e4722d24d9d98ed0923",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": [
                    {
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "id": "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conan_package.tgz"
                    },
                    {
                        "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                        "md5": "95adc888e92d1a888454fae2093c0862",
                        "id": "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conaninfo.txt"
                    },
                    {
                        "sha1": "fe0b6d9343648ae2b60d5c6c4ce765291cc278fb",
                        "md5": "2702b1656a7318c01112b90cca875867",
                        "id": "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conanmanifest.txt"
                    }
                ]
            },
            {
                "id": "PkgA/0.2@user/channel",
                "artifacts": [
                    {
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "name": "conan_sources.tgz"
                    },
                    {
                        "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                        "md5": "00dbccdd251aa5652df8886cf153d2d6",
                        "name": "conanfile.py"
                    },
                    {
                        "sha1": "7ca1713befc9eabcfaaa244133e3e173307705f4",
                        "md5": "d723dfc35eb5a121e401818fdb43b210",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": []
            },
            {
                "id": "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                "artifacts": [
                    {
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "name": "conan_package.tgz"
                    },
                    {
                        "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                        "md5": "95adc888e92d1a888454fae2093c0862",
                        "name": "conaninfo.txt"
                    },
                    {
                        "sha1": "fe0b6d9343648ae2b60d5c6c4ce765291cc278fb",
                        "md5": "2702b1656a7318c01112b90cca875867",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": []
            }
        ]
    }""")

    result = textwrap.dedent("""
    {
        "version": "1.0.1",
        "name": "MyBuildName",
        "number": "42",
        "type": "GENERIC",
        "started": "2019-10-29T10:41:25.000Z",
        "buildAgent": {
            "name": "Conan Client",
            "version": "1.X"
        },
        "modules": [
            {
                "id": "PkgB/0.1@user/channel",
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
                        "sha1": "6cbda4a7286d9bb37eb3a6c97b150ed4939f4095",
                        "md5": "67abd07526f4abdf24f88f443c907f78",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": [
                    {
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "id": "PkgA/0.2@user/channel :: conan_sources.tgz"
                    },
                    {
                        "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                        "md5": "00dbccdd251aa5652df8886cf153d2d6",
                        "id": "PkgA/0.2@user/channel :: conanfile.py"
                    },
                    {
                        "sha1": "7ca1713befc9eabcfaaa244133e3e173307705f4",
                        "md5": "d723dfc35eb5a121e401818fdb43b210",
                        "id": "PkgA/0.2@user/channel :: conanmanifest.txt"
                    }
                ]
            },
            {
                "id": "PkgB/0.1@user/channel:09f152eb7b3e0a6e15a2a3f464245864ae8f8644",
                "artifacts": [
                    {
                        "sha1": "45f961804e3bcc5267a2f6d130b4dcc16e2379ee",
                        "md5": "d4f703971717722bd84c24eccf50b9fd",
                        "name": "conan_package.tgz"
                    },
                    {
                        "sha1": "9525339890e3b484d5e7d8f351957b6c2a28147f",
                        "md5": "fd6b4a992aa1254fa5a404888ed8c7ce",
                        "name": "conaninfo.txt"
                    },
                    {
                        "sha1": "f8f2795005c8fbfbcddae7224888d66a8f47f533",
                        "md5": "c18ffa171f4df3ab4af24dc443320a5a",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": [
                    {
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "id": "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conan_package.tgz"
                    },
                    {
                        "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                        "md5": "95adc888e92d1a888454fae2093c0862",
                        "id": "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conaninfo.txt"
                    },
                    {
                        "sha1": "fe0b6d9343648ae2b60d5c6c4ce765291cc278fb",
                        "md5": "2702b1656a7318c01112b90cca875867",
                        "id": "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conanmanifest.txt"
                    }
                ]
            },
            {
                "id": "PkgA/0.2@user/channel",
                "artifacts": [
                    {
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "name": "conan_sources.tgz"
                    },
                    {
                        "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                        "md5": "00dbccdd251aa5652df8886cf153d2d6",
                        "name": "conanfile.py"
                    },
                    {
                        "sha1": "7ca1713befc9eabcfaaa244133e3e173307705f4",
                        "md5": "d723dfc35eb5a121e401818fdb43b210",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": []
            },
            {
                "id": "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                "artifacts": [
                    {
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "name": "conan_package.tgz"
                    },
                    {
                        "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                        "md5": "95adc888e92d1a888454fae2093c0862",
                        "name": "conaninfo.txt"
                    },
                    {
                        "sha1": "fe0b6d9343648ae2b60d5c6c4ce765291cc278fb",
                        "md5": "2702b1656a7318c01112b90cca875867",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": []
            },
            {
                "id": "PkgC/0.1@user/channel",
                "artifacts": [
                    {
                        "sha1": "410b7df1fd1483a5a7b4c47e67822fc1e3dd533b",
                        "md5": "461fbd5d7e66ce86b8e56fb2524970dc",
                        "name": "conan_sources.tgz"
                    },
                    {
                        "sha1": "a058b1a9366a361d71ea5d67997009f7200de6e1",
                        "md5": "a73be4ec0c7301d2ea2dacc873df5483",
                        "name": "conanfile.py"
                    },
                    {
                        "sha1": "594ff68dadb4cbeb36ff724286032698098b41e7",
                        "md5": "19052f117ce1513c3a815f41fd704c24",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": [
                    {
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "id": "PkgA/0.2@user/channel :: conan_sources.tgz"
                    },
                    {
                        "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                        "md5": "00dbccdd251aa5652df8886cf153d2d6",
                        "id": "PkgA/0.2@user/channel :: conanfile.py"
                    },
                    {
                        "sha1": "7ca1713befc9eabcfaaa244133e3e173307705f4",
                        "md5": "d723dfc35eb5a121e401818fdb43b210",
                        "id": "PkgA/0.2@user/channel :: conanmanifest.txt"
                    }
                ]
            },
            {
                "id": "PkgC/0.1@user/channel:09f152eb7b3e0a6e15a2a3f464245864ae8f8644",
                "artifacts": [
                    {
                        "sha1": "0b6a6755369820f66d6a858d3b44775fb1b38f54",
                        "md5": "c1f3a9ff4ee80ab5e5492c1c381dff56",
                        "name": "conan_package.tgz"
                    },
                    {
                        "sha1": "6bce988c0cfc1d17588c0fddac573066afd8d26d",
                        "md5": "bde279efd0a24162425017d937fe8484",
                        "name": "conaninfo.txt"
                    },
                    {
                        "sha1": "6a85f6893f316433cd935abad31c4daf80d09884",
                        "md5": "5996a968f13f4e4722d24d9d98ed0923",
                        "name": "conanmanifest.txt"
                    }
                ],
                "dependencies": [
                    {
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "id": "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conan_package.tgz"
                    },
                    {
                        "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                        "md5": "95adc888e92d1a888454fae2093c0862",
                        "id": "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conaninfo.txt"
                    },
                    {
                        "sha1": "fe0b6d9343648ae2b60d5c6c4ce765291cc278fb",
                        "md5": "2702b1656a7318c01112b90cca875867",
                        "id": "PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 :: conanmanifest.txt"
                    }
                ]
            }
        ]
    }""")

    def update_build_info_test(self):
        tmp_dir = temp_folder()
        file1 = os.path.join(tmp_dir, "buildinfo1.json")
        file2 = os.path.join(tmp_dir, "buildinfo2.json")
        outfile = os.path.join(tmp_dir, "mergedbuildinfo.json")
        save(file1, self.buildinfo1)
        save(file2, self.buildinfo2)
        update_build_info([file1, file2], outfile)
        with open(outfile, "r") as json_data:
            mergedinfo = json.load(json_data)
            res_json = json.loads(self.result)

        self.assertEqual(mergedinfo["version"], res_json["version"])
        self.assertEqual(mergedinfo["name"], res_json["name"])
        self.assertEqual(mergedinfo["number"], res_json["number"])
        self.assertEqual(mergedinfo["type"], res_json["type"])
        self.assertEqual(mergedinfo["started"], res_json["started"])
        self.assertDictEqual(mergedinfo["buildAgent"], res_json["buildAgent"])
        for index in range(2):
            self.assertEqual(mergedinfo["modules"][index]["id"],
                             res_json["modules"][index]["id"])
