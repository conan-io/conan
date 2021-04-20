import json
import os
import textwrap
import unittest

from mock import patch, Mock

from conans.build_info.build_info import update_build_info, publish_build_info
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.tools import save
from conans import __version__


class BuildInfoTest(unittest.TestCase):
    buildinfo1 = textwrap.dedent("""
    {{
        "version": "1.0.1",
        "name": "MyBuildName",
        "number": "42",
        "type": "GENERIC",
        "started": "2019-10-29T10:41:25.000Z",
        "buildAgent": {{
            "name": "conan",
            "version": "{}"
        }},
        "modules": [
            {{
                "type": "conan",
                "repository": "develop",
                "id": "PkgB/0.1@user/channel#59ba6f9d5109a2692330b3c6b961313b",
                "artifacts": [
                    {{
                        "sha1": "aba8527a2c4fc142cf5262298824d3680ecb057f",
                        "md5": "aad124317706ef90df47686329be8e2b",
                        "name": "conan_sources.tgz",
                        "path": "user/PkgB/0.1/channel/59ba6f9d5109a2692330b3c6b961313b/export"
                    }},
                    {{
                        "sha1": "a058b1a9366a361d71ea5d67997009f7200de6e1",
                        "md5": "a73be4ec0c7301d2ea2dacc873df5483",
                        "name": "conanfile.py",
                        "path": "user/PkgB/0.1/channel/59ba6f9d5109a2692330b3c6b961313b/export"
                    }},
                    {{
                        "sha1": "6cbda4a7286d9bb37eb3a6c97b150ed4939f4095",
                        "md5": "67abd07526f4abdf24f88f443c907f78",
                        "name": "conanmanifest.txt",
                        "path": "user/PkgB/0.1/channel/59ba6f9d5109a2692330b3c6b961313b/export"
                    }}
                ],
                "dependencies": [
                    {{
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e :: conan_sources.tgz"
                    }},
                    {{
                        "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                        "md5": "00dbccdd251aa5652df8886cf153d2d6",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e :: conanfile.py"
                    }},
                    {{
                        "sha1": "7ca1713befc9eabcfaaa244133e3e173307705f4",
                        "md5": "d723dfc35eb5a121e401818fdb43b210",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e :: conanmanifest.txt"
                    }}
                ]
            }},
            {{
                "type": "conan",
                "repository": "develop",
                "id": "PkgB/0.1@user/channel#59ba6f9d5109a2692330b3c6b961313b:451532304ef8fa47e00fa54ca3f94d06c6e0e57f#692a3a14fb5860c377c1dff609bc90cb",
                "artifacts": [
                    {{
                        "sha1": "45f961804e3bcc5267a2f6d130b4dcc16e2379ee",
                        "md5": "d4f703971717722bd84c24eccf50b9fd",
                        "name": "conan_package.tgz",
                        "path": "user/PkgB/0.1/channel/59ba6f9d5109a2692330b3c6b961313b/package/451532304ef8fa47e00fa54ca3f94d06c6e0e57f/692a3a14fb5860c377c1dff609bc90cb"
                    }},
                    {{
                        "sha1": "9525339890e3b484d5e7d8f351957b6c2a28147f",
                        "md5": "fd6b4a992aa1254fa5a404888ed8c7ce",
                        "name": "conaninfo.txt",
                        "path": "user/PkgB/0.1/channel/59ba6f9d5109a2692330b3c6b961313b/package/451532304ef8fa47e00fa54ca3f94d06c6e0e57f/692a3a14fb5860c377c1dff609bc90cb"
                    }},
                    {{
                        "sha1": "f8f2795005c8fbfbcddae7224888d66a8f47f533",
                        "md5": "c18ffa171f4df3ab4af24dc443320a5a",
                        "name": "conanmanifest.txt",
                        "path": "user/PkgB/0.1/channel/59ba6f9d5109a2692330b3c6b961313b/package/451532304ef8fa47e00fa54ca3f94d06c6e0e57f/692a3a14fb5860c377c1dff609bc90cb"
                    }}
                ],
                "dependencies": [
                    {{
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e:9db1d964f4a0e5590a43a0c634a3196a8a3eca3b#2d0052a59a49a706c057ebeb107292e6 :: conan_package.tgz"
                    }},
                    {{
                        "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                        "md5": "95adc888e92d1a888454fae2093c0862",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e:9db1d964f4a0e5590a43a0c634a3196a8a3eca3b#2d0052a59a49a706c057ebeb107292e6 :: conaninfo.txt"
                    }},
                    {{
                        "sha1": "fe0b6d9343648ae2b60d5c6c4ce765291cc278fb",
                        "md5": "2702b1656a7318c01112b90cca875867",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e:9db1d964f4a0e5590a43a0c634a3196a8a3eca3b#2d0052a59a49a706c057ebeb107292e6 :: conanmanifest.txt"
                    }}
                ]
            }},
            {{
                "type": "conan",
                "repository": "develop",
                "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e",
                "artifacts": [
                    {{
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "name": "conan_sources.tgz",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/export"
                    }},
                    {{
                        "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                        "md5": "00dbccdd251aa5652df8886cf153d2d6",
                        "name": "conanfile.py",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/export"
                    }},
                    {{
                        "sha1": "7ca1713befc9eabcfaaa244133e3e173307705f4",
                        "md5": "d723dfc35eb5a121e401818fdb43b210",
                        "name": "conanmanifest.txt",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/export"
                    }}
                ],
                "dependencies": []
            }},
            {{
                "type": "conan",
                "repository": "develop",
                "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e:9db1d964f4a0e5590a43a0c634a3196a8a3eca3b#2d0052a59a49a706c057ebeb107292e6",
                "artifacts": [
                    {{
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "name": "conan_package.tgz",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/package/9db1d964f4a0e5590a43a0c634a3196a8a3eca3b/2d0052a59a49a706c057ebeb107292e6"
                    }},
                    {{
                        "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                        "md5": "95adc888e92d1a888454fae2093c0862",
                        "name": "conaninfo.txt",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/package/9db1d964f4a0e5590a43a0c634a3196a8a3eca3b/2d0052a59a49a706c057ebeb107292e6"
                    }},
                    {{
                        "sha1": "fe0b6d9343648ae2b60d5c6c4ce765291cc278fb",
                        "md5": "2702b1656a7318c01112b90cca875867",
                        "name": "conanmanifest.txt",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/package/9db1d964f4a0e5590a43a0c634a3196a8a3eca3b/2d0052a59a49a706c057ebeb107292e6"
                    }}
                ],
                "dependencies": []
            }}
        ]
    }}""".format(__version__))

    buildinfo2 = textwrap.dedent("""
    {{
        "version": "1.0.1",
        "name": "MyBuildName",
        "number": "42",
        "type": "GENERIC",
        "started": "2019-10-29T10:41:25.000Z",
        "buildAgent": {{
            "name": "conan",
            "version": "{}"
        }},
        "modules": [
            {{
                "type": "conan",
                "repository": "develop",
                "id": "PkgC/0.1@user/channel#0b1a78f5925f62480ed2d97002e926fa",
                "artifacts": [
                    {{
                        "sha1": "410b7df1fd1483a5a7b4c47e67822fc1e3dd533b",
                        "md5": "461fbd5d7e66ce86b8e56fb2524970dc",
                        "name": "conan_sources.tgz",
                        "path": "user/PkgC/0.1/channel/0b1a78f5925f62480ed2d97002e926fa/export"
                    }},
                    {{
                        "sha1": "a058b1a9366a361d71ea5d67997009f7200de6e1",
                        "md5": "a73be4ec0c7301d2ea2dacc873df5483",
                        "name": "conanfile.py",
                        "path": "user/PkgC/0.1/channel/0b1a78f5925f62480ed2d97002e926fa/export"
                    }},
                    {{
                        "sha1": "594ff68dadb4cbeb36ff724286032698098b41e7",
                        "md5": "19052f117ce1513c3a815f41fd704c24",
                        "name": "conanmanifest.txt",
                        "path": "user/PkgC/0.1/channel/0b1a78f5925f62480ed2d97002e926fa/export"
                    }}
                ],
                "dependencies": [
                    {{
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e :: conan_sources.tgz"
                    }},
                    {{
                        "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                        "md5": "00dbccdd251aa5652df8886cf153d2d6",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e :: conanfile.py"
                    }},
                    {{
                        "sha1": "7ca1713befc9eabcfaaa244133e3e173307705f4",
                        "md5": "d723dfc35eb5a121e401818fdb43b210",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e :: conanmanifest.txt"
                    }}
                ]
            }},
            {{
                "type": "conan",
                "repository": "develop",
                "id": "PkgC/0.1@user/channel#0b1a78f5925f62480ed2d97002e926fa:6a83d7f783e7ee89a83cf2fe72b5f5f67538e2a6#28fb6fe2b23c481d38b88d1521374f3e",
                "artifacts": [
                    {{
                        "sha1": "0b6a6755369820f66d6a858d3b44775fb1b38f54",
                        "md5": "c1f3a9ff4ee80ab5e5492c1c381dff56",
                        "name": "conan_package.tgz",
                        "path": "user/PkgC/0.1/channel/0b1a78f5925f62480ed2d97002e926fa/package/6a83d7f783e7ee89a83cf2fe72b5f5f67538e2a6/28fb6fe2b23c481d38b88d1521374f3e"
                    }},
                    {{
                        "sha1": "6bce988c0cfc1d17588c0fddac573066afd8d26d",
                        "md5": "bde279efd0a24162425017d937fe8484",
                        "name": "conaninfo.txt",
                        "path": "user/PkgC/0.1/channel/0b1a78f5925f62480ed2d97002e926fa/package/6a83d7f783e7ee89a83cf2fe72b5f5f67538e2a6/28fb6fe2b23c481d38b88d1521374f3e"
                    }},
                    {{
                        "sha1": "6a85f6893f316433cd935abad31c4daf80d09884",
                        "md5": "5996a968f13f4e4722d24d9d98ed0923",
                        "name": "conanmanifest.txt",
                        "path": "user/PkgC/0.1/channel/0b1a78f5925f62480ed2d97002e926fa/package/6a83d7f783e7ee89a83cf2fe72b5f5f67538e2a6/28fb6fe2b23c481d38b88d1521374f3e"
                    }}
                ],
                "dependencies": [
                    {{
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e:9db1d964f4a0e5590a43a0c634a3196a8a3eca3b#2d0052a59a49a706c057ebeb107292e6 :: conan_package.tgz"
                    }},
                    {{
                        "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                        "md5": "95adc888e92d1a888454fae2093c0862",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e:9db1d964f4a0e5590a43a0c634a3196a8a3eca3b#2d0052a59a49a706c057ebeb107292e6 :: conaninfo.txt"
                    }},
                    {{
                        "sha1": "fe0b6d9343648ae2b60d5c6c4ce765291cc278fb",
                        "md5": "2702b1656a7318c01112b90cca875867",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e:9db1d964f4a0e5590a43a0c634a3196a8a3eca3b#2d0052a59a49a706c057ebeb107292e6 :: conanmanifest.txt"
                    }}
                ]
            }},
            {{
                "type": "conan",
                "repository": "develop",
                "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e",
                "artifacts": [
                    {{
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "name": "conan_sources.tgz",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/export"
                    }},
                    {{
                        "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                        "md5": "00dbccdd251aa5652df8886cf153d2d6",
                        "name": "conanfile.py",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/export"
                    }},
                    {{
                        "sha1": "7ca1713befc9eabcfaaa244133e3e173307705f4",
                        "md5": "d723dfc35eb5a121e401818fdb43b210",
                        "name": "conanmanifest.txt",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/export"
                    }}
                ],
                "dependencies": []
            }},
            {{
                "type": "conan",
                "repository": "develop",
                "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e:9db1d964f4a0e5590a43a0c634a3196a8a3eca3b#2d0052a59a49a706c057ebeb107292e6",
                "artifacts": [
                    {{
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "name": "conan_package.tgz",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/package/9db1d964f4a0e5590a43a0c634a3196a8a3eca3b/2d0052a59a49a706c057ebeb107292e6"
                    }},
                    {{
                        "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                        "md5": "95adc888e92d1a888454fae2093c0862",
                        "name": "conaninfo.txt",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/package/9db1d964f4a0e5590a43a0c634a3196a8a3eca3b/2d0052a59a49a706c057ebeb107292e6"
                    }},
                    {{
                        "sha1": "fe0b6d9343648ae2b60d5c6c4ce765291cc278fb",
                        "md5": "2702b1656a7318c01112b90cca875867",
                        "name": "conanmanifest.txt",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/package/9db1d964f4a0e5590a43a0c634a3196a8a3eca3b/2d0052a59a49a706c057ebeb107292e6"
                    }}
                ],
                "dependencies": []
            }}
        ]
    }}""".format(__version__))

    result = textwrap.dedent("""
    {{
        "version": "1.0.1",
        "name": "MyBuildName",
        "number": "42",
        "type": "GENERIC",
        "started": "2019-10-29T10:41:25.000Z",
        "buildAgent": {{
            "name": "conan",
            "version": "{}"
        }},
        "modules": [
            {{
                "type": "conan",
                "repository": "develop",
                "id": "PkgB/0.1@user/channel#59ba6f9d5109a2692330b3c6b961313b",
                "artifacts": [
                    {{
                        "sha1": "aba8527a2c4fc142cf5262298824d3680ecb057f",
                        "md5": "aad124317706ef90df47686329be8e2b",
                        "name": "conan_sources.tgz",
                        "path": "user/PkgB/0.1/channel/59ba6f9d5109a2692330b3c6b961313b/export"
                    }},
                    {{
                        "sha1": "a058b1a9366a361d71ea5d67997009f7200de6e1",
                        "md5": "a73be4ec0c7301d2ea2dacc873df5483",
                        "name": "conanfile.py",
                        "path": "user/PkgB/0.1/channel/59ba6f9d5109a2692330b3c6b961313b/export"
                    }},
                    {{
                        "sha1": "6cbda4a7286d9bb37eb3a6c97b150ed4939f4095",
                        "md5": "67abd07526f4abdf24f88f443c907f78",
                        "name": "conanmanifest.txt",
                        "path": "user/PkgB/0.1/channel/59ba6f9d5109a2692330b3c6b961313b/export"
                    }}
                ],
                "dependencies": [
                    {{
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e :: conan_sources.tgz"
                    }},
                    {{
                        "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                        "md5": "00dbccdd251aa5652df8886cf153d2d6",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e :: conanfile.py"
                    }},
                    {{
                        "sha1": "7ca1713befc9eabcfaaa244133e3e173307705f4",
                        "md5": "d723dfc35eb5a121e401818fdb43b210",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e :: conanmanifest.txt"
                    }}
                ]
            }},
            {{
                "type": "conan",
                "repository": "develop",
                "id": "PkgB/0.1@user/channel#59ba6f9d5109a2692330b3c6b961313b:451532304ef8fa47e00fa54ca3f94d06c6e0e57f#692a3a14fb5860c377c1dff609bc90cb",
                "artifacts": [
                    {{
                        "sha1": "45f961804e3bcc5267a2f6d130b4dcc16e2379ee",
                        "md5": "d4f703971717722bd84c24eccf50b9fd",
                        "name": "conan_package.tgz",
                        "path": "user/PkgB/0.1/channel/59ba6f9d5109a2692330b3c6b961313b/package/451532304ef8fa47e00fa54ca3f94d06c6e0e57f/692a3a14fb5860c377c1dff609bc90cb"
                    }},
                    {{
                        "sha1": "9525339890e3b484d5e7d8f351957b6c2a28147f",
                        "md5": "fd6b4a992aa1254fa5a404888ed8c7ce",
                        "name": "conaninfo.txt",
                        "path": "user/PkgB/0.1/channel/59ba6f9d5109a2692330b3c6b961313b/package/451532304ef8fa47e00fa54ca3f94d06c6e0e57f/692a3a14fb5860c377c1dff609bc90cb"
                    }},
                    {{
                        "sha1": "f8f2795005c8fbfbcddae7224888d66a8f47f533",
                        "md5": "c18ffa171f4df3ab4af24dc443320a5a",
                        "name": "conanmanifest.txt",
                        "path": "user/PkgB/0.1/channel/59ba6f9d5109a2692330b3c6b961313b/package/451532304ef8fa47e00fa54ca3f94d06c6e0e57f/692a3a14fb5860c377c1dff609bc90cb"
                    }}
                ],
                "dependencies": [
                    {{
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e:9db1d964f4a0e5590a43a0c634a3196a8a3eca3b#2d0052a59a49a706c057ebeb107292e6 :: conan_package.tgz"
                    }},
                    {{
                        "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                        "md5": "95adc888e92d1a888454fae2093c0862",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e:9db1d964f4a0e5590a43a0c634a3196a8a3eca3b#2d0052a59a49a706c057ebeb107292e6 :: conaninfo.txt"
                    }},
                    {{
                        "sha1": "fe0b6d9343648ae2b60d5c6c4ce765291cc278fb",
                        "md5": "2702b1656a7318c01112b90cca875867",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e:9db1d964f4a0e5590a43a0c634a3196a8a3eca3b#2d0052a59a49a706c057ebeb107292e6 :: conanmanifest.txt"
                    }}
                ]
            }},
            {{
                "type": "conan",
                "repository": "develop",
                "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e",
                "artifacts": [
                    {{
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "name": "conan_sources.tgz",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/export"
                    }},
                    {{
                        "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                        "md5": "00dbccdd251aa5652df8886cf153d2d6",
                        "name": "conanfile.py",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/export"
                    }},
                    {{
                        "sha1": "7ca1713befc9eabcfaaa244133e3e173307705f4",
                        "md5": "d723dfc35eb5a121e401818fdb43b210",
                        "name": "conanmanifest.txt",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/export"
                    }}
                ],
                "dependencies": []
            }},
            {{
                "type": "conan",
                "repository": "develop",
                "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e:9db1d964f4a0e5590a43a0c634a3196a8a3eca3b#2d0052a59a49a706c057ebeb107292e6",
                "artifacts": [
                    {{
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "name": "conan_package.tgz",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/package/9db1d964f4a0e5590a43a0c634a3196a8a3eca3b/2d0052a59a49a706c057ebeb107292e6"
                    }},
                    {{
                        "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                        "md5": "95adc888e92d1a888454fae2093c0862",
                        "name": "conaninfo.txt",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/package/9db1d964f4a0e5590a43a0c634a3196a8a3eca3b/2d0052a59a49a706c057ebeb107292e6"
                    }},
                    {{
                        "sha1": "fe0b6d9343648ae2b60d5c6c4ce765291cc278fb",
                        "md5": "2702b1656a7318c01112b90cca875867",
                        "name": "conanmanifest.txt",
                        "path": "user/PkgA/0.2/channel/26386415fb6f92bb9413d60903e5181e/package/9db1d964f4a0e5590a43a0c634a3196a8a3eca3b/2d0052a59a49a706c057ebeb107292e6"
                    }}
                ],
                "dependencies": []
            }},
            {{
                "type": "conan",
                "repository": "develop",
                "id": "PkgC/0.1@user/channel#0b1a78f5925f62480ed2d97002e926fa",
                "artifacts": [
                    {{
                        "sha1": "410b7df1fd1483a5a7b4c47e67822fc1e3dd533b",
                        "md5": "461fbd5d7e66ce86b8e56fb2524970dc",
                        "name": "conan_sources.tgz",
                        "path": "user/PkgC/0.1/channel/0b1a78f5925f62480ed2d97002e926fa/export"
                    }},
                    {{
                        "sha1": "a058b1a9366a361d71ea5d67997009f7200de6e1",
                        "md5": "a73be4ec0c7301d2ea2dacc873df5483",
                        "name": "conanfile.py",
                        "path": "user/PkgC/0.1/channel/0b1a78f5925f62480ed2d97002e926fa/export"
                    }},
                    {{
                        "sha1": "594ff68dadb4cbeb36ff724286032698098b41e7",
                        "md5": "19052f117ce1513c3a815f41fd704c24",
                        "name": "conanmanifest.txt",
                        "path": "user/PkgC/0.1/channel/0b1a78f5925f62480ed2d97002e926fa/export"
                    }}
                ],
                "dependencies": [
                    {{
                        "sha1": "def7797033b5b46ca063aaaf21dc7a9c1b93a35a",
                        "md5": "89b684b95f6f5c7a8e2fda664be22c5a",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e :: conan_sources.tgz"
                    }},
                    {{
                        "sha1": "7bd4da1c70ca29637b159a0131a8b886cfaeeb27",
                        "md5": "00dbccdd251aa5652df8886cf153d2d6",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e :: conanfile.py"
                    }},
                    {{
                        "sha1": "7ca1713befc9eabcfaaa244133e3e173307705f4",
                        "md5": "d723dfc35eb5a121e401818fdb43b210",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e :: conanmanifest.txt"
                    }}
                ]
            }},
            {{
                "type": "conan",
                "repository": "develop",
                "id": "PkgC/0.1@user/channel#0b1a78f5925f62480ed2d97002e926fa:6a83d7f783e7ee89a83cf2fe72b5f5f67538e2a6#28fb6fe2b23c481d38b88d1521374f3e",
                "artifacts": [
                    {{
                        "sha1": "0b6a6755369820f66d6a858d3b44775fb1b38f54",
                        "md5": "c1f3a9ff4ee80ab5e5492c1c381dff56",
                        "name": "conan_package.tgz",
                        "path": "user/PkgC/0.1/channel/0b1a78f5925f62480ed2d97002e926fa/package/6a83d7f783e7ee89a83cf2fe72b5f5f67538e2a6/28fb6fe2b23c481d38b88d1521374f3e"
                    }},
                    {{
                        "sha1": "6bce988c0cfc1d17588c0fddac573066afd8d26d",
                        "md5": "bde279efd0a24162425017d937fe8484",
                        "name": "conaninfo.txt",
                        "path": "user/PkgC/0.1/channel/0b1a78f5925f62480ed2d97002e926fa/package/6a83d7f783e7ee89a83cf2fe72b5f5f67538e2a6/28fb6fe2b23c481d38b88d1521374f3e"
                    }},
                    {{
                        "sha1": "6a85f6893f316433cd935abad31c4daf80d09884",
                        "md5": "5996a968f13f4e4722d24d9d98ed0923",
                        "name": "conanmanifest.txt",
                        "path": "user/PkgC/0.1/channel/0b1a78f5925f62480ed2d97002e926fa/package/6a83d7f783e7ee89a83cf2fe72b5f5f67538e2a6/28fb6fe2b23c481d38b88d1521374f3e"
                    }}
                ],
                "dependencies": [
                    {{
                        "sha1": "a96d326d2449a103a4f9e6d81018ffd411b3f4a1",
                        "md5": "43c402f3ad0cc9dfa89c5be37bf9b7e5",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e:9db1d964f4a0e5590a43a0c634a3196a8a3eca3b#2d0052a59a49a706c057ebeb107292e6 :: conan_package.tgz"
                    }},
                    {{
                        "sha1": "2f452380f6ec5db0baab369d0bc4286793710ca3",
                        "md5": "95adc888e92d1a888454fae2093c0862",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e:9db1d964f4a0e5590a43a0c634a3196a8a3eca3b#2d0052a59a49a706c057ebeb107292e6 :: conaninfo.txt"
                    }},
                    {{
                        "sha1": "fe0b6d9343648ae2b60d5c6c4ce765291cc278fb",
                        "md5": "2702b1656a7318c01112b90cca875867",
                        "id": "PkgA/0.2@user/channel#26386415fb6f92bb9413d60903e5181e:9db1d964f4a0e5590a43a0c634a3196a8a3eca3b#2d0052a59a49a706c057ebeb107292e6 :: conanmanifest.txt"
                    }}
                ]
            }}
        ]
    }}""".format(__version__))

    def test_update_build_info(self):
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
        self.assertDictEqual(mergedinfo["buildAgent"], res_json["buildAgent"])

        for index in range(len(mergedinfo["modules"])):
            self.assertEqual(mergedinfo["modules"][index]["id"],
                             res_json["modules"][index]["id"])
            self.assertEqual(mergedinfo["modules"][index]["type"],
                             res_json["modules"][index]["type"])
            self.assertEqual(mergedinfo["modules"][index]["repository"],
                             res_json["modules"][index]["repository"])


# https://github.com/conan-io/conan/issues/8802
def test_publish_artifactory_context():
    client = TestClient()
    client.save({"build_info.json": ""})

    def mock_put_no_artifactory(url, data=None, **kwargs):
        mock_put = Mock()
        if "artifactory" not in url:
            mock_put.status_code = 204
        else:
            mock_put.status_code = 501
        return mock_put

    def mock_put_artifactory(url, data=None, **kwargs):
        mock_put = Mock()
        if "artifactory" in url:
            mock_put.status_code = 204
        else:
            mock_put.status_code = 501
        return mock_put

    with patch("conans.build_info.build_info.requests.put", side_effect=mock_put_no_artifactory):
        publish_build_info(os.path.join(client.current_folder, "build_info.json"),
                           "http://fakeurl:8081", "user", "password", "")

    with patch("conans.build_info.build_info.requests.put", side_effect=mock_put_artifactory):
        publish_build_info(os.path.join(client.current_folder, "build_info.json"),
                           "http://fakeurl:8081/artifactory", "user", "password", "")
