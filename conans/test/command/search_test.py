import unittest
from conans.test.tools import TestClient
from conans.paths import PACKAGES_FOLDER, CONANINFO


conan_vars1 = '''
[settings]
    arch=x64
    os=Windows
    version=8.1
[options]
    use_Qt=True
'''

conan_vars2 = '''
[options]
    use_OpenGL=True
[settings]
    arch=x64
    os=Ubuntu
    version=15.04
'''

conan_vars3 = '''
[options]
    HAVE_TESTS=True
    USE_CONFIG=False
[settings]
    os=Darwin
'''

conan_vars4 = """[settings]
  os=Windows
  arch=x86_64
  compiler=gcc
[options]
  language=1
[requires]
  Hello2/0.1@lasote/stable
  OpenSSL/2.10@lasote/testing
  HelloInfo1/0.45@fenix/testing
"""


class SearchTest(unittest.TestCase):

    def local_test(self):
        client = TestClient()

        # No conans created
        client.run("search")
        output = client.user_io.out
        self.assertIn('There are no packages', output)

        # Conans with and without packages created
        root_folder1 = 'Hello/1.4.10/fenix/testing'
        root_folder2 = 'helloTest/1.4.10/fenix/stable'
        root_folder3 = 'Bye/0.14/fenix/testing'
        root_folder4 = 'NodeInfo/1.0.2/fenix/stable'
        root_folder5 = 'MissFile/1.0.2/fenix/stable'

        client.save({"Empty/1.10/fake/test/reg/fake.txt": "//",
                     "%s/%s/d91960d4c06b38/%s" % (root_folder1,
                                                  PACKAGES_FOLDER,
                                                  CONANINFO): conan_vars1,
                     "%s/%s/a44f541cd44w57/%s" % (root_folder2,
                                                  PACKAGES_FOLDER,
                                                  CONANINFO): conan_vars2,
                     "%s/%s/e4f7vdwcv4w55d/%s" % (root_folder3,
                                                  PACKAGES_FOLDER,
                                                  CONANINFO): conan_vars3,
                     "%s/%s/e4f7vdwcv4w55d/%s" % (root_folder4,
                                                  PACKAGES_FOLDER,
                                                  CONANINFO): conan_vars4,
                     "%s/%s/e4f7vdwcv4w55d/%s" % (root_folder5,
                                                  PACKAGES_FOLDER,
                                                  "hello.txt"): "Hello"}, client.paths.store)

        client.run("search -x")
        self.assertEqual("""Existing packages info:

Bye/0.14@fenix/testing
    Package_ID: e4f7vdwcv4w55d
        [options]
            HAVE_TESTS=True
            USE_CONFIG=False
        [settings]
            os=Darwin
        [requirements]
Empty/1.10@fake/test
    There are no packages
Hello/1.4.10@fenix/testing
    Package_ID: d91960d4c06b38
        [options]
            use_Qt=True
        [settings]
            arch=x64
            os=Windows
            version=8.1
        [requirements]
MissFile/1.0.2@fenix/stable
    There are no packages
NodeInfo/1.0.2@fenix/stable
    Package_ID: e4f7vdwcv4w55d
        [options]
            language=1
        [settings]
            arch=x86_64
            compiler=gcc
            os=Windows
        [requirements]
helloTest/1.4.10@fenix/stable
    Package_ID: a44f541cd44w57
        [options]
            use_OpenGL=True
        [settings]
            arch=x64
            os=Ubuntu
            version=15.04
        [requirements]
""", client.user_io.out)

        client.run("search -v")
        self.assertEqual("""Existing packages info:

Bye/0.14@fenix/testing
    Package_ID: e4f7vdwcv4w55d
            (Darwin)
Empty/1.10@fake/test
    There are no packages
Hello/1.4.10@fenix/testing
    Package_ID: d91960d4c06b38
            (x64, Windows, 8.1)
MissFile/1.0.2@fenix/stable
    There are no packages
NodeInfo/1.0.2@fenix/stable
    Package_ID: e4f7vdwcv4w55d
            (x86_64, gcc, Windows)
helloTest/1.4.10@fenix/stable
    Package_ID: a44f541cd44w57
            (x64, Ubuntu, 15.04)
""", client.user_io.out)

        client.run("search ")
        self.assertEqual("""Existing packages info:

Bye/0.14@fenix/testing
Empty/1.10@fake/test
Hello/1.4.10@fenix/testing
MissFile/1.0.2@fenix/stable
NodeInfo/1.0.2@fenix/stable
helloTest/1.4.10@fenix/stable
""", client.user_io.out)

        client.run("search Bye/* -x")
        self.assertEqual("""Existing packages info:

Bye/0.14@fenix/testing
    Package_ID: e4f7vdwcv4w55d
        [options]
            HAVE_TESTS=True
            USE_CONFIG=False
        [settings]
            os=Darwin
        [requirements]
""", client.user_io.out)

        # bad pattern
        client.run("search OpenCV/* -v")
        self.assertIn("There are no packages matching the OpenCV/* pattern", client.user_io.out)

        # pattern case-sensitive
        client.run("search hello* --case-sensitive -v")
        self.assertIn("helloTest/1.4.10@fenix/stable", client.user_io.out)
        self.assertNotIn("Empty/1.10@fake/test", client.user_io.out)
        self.assertNotIn("Hello/1.4.10@fenix/testing", client.user_io.out)
        self.assertNotIn("NodeInfo/1.0.2@fenix/stable", client.user_io.out)

        # Package search
        client.run("search -p e4* -v")
        self.assertIn('''Bye/0.14@fenix/testing
    Package_ID: e4f7vdwcv4w55d
            (Darwin)
NodeInfo/1.0.2@fenix/stable
    Package_ID: e4f7vdwcv4w55d
            (x86_64, gcc, Windows)''', client.user_io.out)

        client.run("search -p d9 -v")
        self.assertIn('''Hello/1.4.10@fenix/testing
    Package_ID: d91960d4c06b38
            (x64, Windows, 8.1)''', client.user_io.out)

        client.run("search Bye/0.14@fenix/testing -p e4* -v")
        self.assertNotIn('''NodeInfo/1.0.2@fenix/stable''', client.user_io.out)
