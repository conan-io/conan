import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.paths import PACKAGES_FOLDER, CONANINFO, EXPORT_FOLDER, CONAN_MANIFEST
import os
from conans.model.manifest import FileTreeManifest
import shutil
from conans import COMPLEX_SEARCH_CAPABILITY


conan_vars1 = '''
[settings]
    arch=x64
    os=Windows
    compiler=Visual Studio
    compiler.version=8.1
[options]
    use_Qt=True
[full_requires]
  Hello2/0.1@lasote/stable:11111
  OpenSSL/2.10@lasote/testing:2222
  HelloInfo1/0.45@fenix/testing:33333
'''

conan_vars1b = '''
[settings]
    arch=x86
    compiler=gcc
    compiler.version=4.3
    compiler.libcxx=libstdc++
[options]
    use_Qt=True
'''

conan_vars1c = '''
[settings]
    os=Linux
    arch=x86
    compiler=gcc
    compiler.version=4.5
    compiler.libcxx=libstdc++11
[options]
    use_Qt=False
[full_requires]
  Hello2/0.1@lasote/stable:11111
  OpenSSL/2.10@lasote/testing:2222
  HelloInfo1/0.45@fenix/testing:33333
[recipe_hash]
  d41d8cd98f00b204e9800998ecf8427e
'''  # The recipe_hash correspond to the faked conanmanifests in export

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
[full_requires]
  Hello2/0.1@lasote/stable:11111
  OpenSSL/2.10@lasote/testing:2222
  HelloInfo1/0.45@fenix/testing:33333
"""


class SearchTest(unittest.TestCase):

    def setUp(self):
        self.servers = {"local": TestServer(server_capabilities=[]),
                        "search_able": TestServer(server_capabilities=[COMPLEX_SEARCH_CAPABILITY])}
        self.client = TestClient(servers=self.servers)

        # No conans created
        self.client.run("search")
        output = self.client.user_io.out
        self.assertIn('There are no packages', output)

        # Conans with and without packages created
        self.root_folder1 = 'Hello/1.4.10/fenix/testing'
        root_folder2 = 'helloTest/1.4.10/fenix/stable'
        root_folder3 = 'Bye/0.14/fenix/testing'
        root_folder4 = 'NodeInfo/1.0.2/fenix/stable'
        root_folder5 = 'MissFile/1.0.2/fenix/stable'
        root_folder11 = 'Hello/1.4.11/fenix/testing'
        root_folder12 = 'Hello/1.4.12/fenix/testing'

        self.client.save({"Empty/1.10/fake/test/reg/fake.txt": "//",
                          "%s/%s/WindowsPackageSHA/%s" % (self.root_folder1,
                                                          PACKAGES_FOLDER,
                                                          CONANINFO): conan_vars1,
                          "%s/%s/WindowsPackageSHA/%s" % (root_folder11,
                                                          PACKAGES_FOLDER,
                                                          CONANINFO): conan_vars1,
                          "%s/%s/WindowsPackageSHA/%s" % (root_folder12,
                                                          PACKAGES_FOLDER,
                                                          CONANINFO): conan_vars1,
                          "%s/%s/PlatformIndependantSHA/%s" % (self.root_folder1,
                                                               PACKAGES_FOLDER,
                                                               CONANINFO): conan_vars1b,
                          "%s/%s/LinuxPackageSHA/%s" % (self.root_folder1,
                                                        PACKAGES_FOLDER,
                                                        CONANINFO): conan_vars1c,
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
                                                       "hello.txt"): "Hello"},
                         self.client.paths.store)

        # Fake some manifests to be able to calculate recipe hash
        fake_manifest = FileTreeManifest(1212, {})
        self.client.save({os.path.join(self.root_folder1, EXPORT_FOLDER, CONAN_MANIFEST): str(fake_manifest),
                          os.path.join(root_folder2, EXPORT_FOLDER, CONAN_MANIFEST): str(fake_manifest),
                          os.path.join(root_folder3, EXPORT_FOLDER, CONAN_MANIFEST): str(fake_manifest),
                          os.path.join(root_folder4, EXPORT_FOLDER, CONAN_MANIFEST): str(fake_manifest),
                          },
                         self.client.paths.store)

    def recipe_search_test(self):
        self.client.run("search Hello*")
        self.assertEquals("Existing package recipes:\n\n"
                          "Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n"
                          "helloTest/1.4.10@fenix/stable\n", self.client.user_io.out)

        self.client.run("search Hello* --case-sensitive")
        self.assertEquals("Existing package recipes:\n\n"
                          "Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n",
                          self.client.user_io.out)

        self.client.run("search *fenix* --case-sensitive")
        self.assertEquals("Existing package recipes:\n\n"
                          "Bye/0.14@fenix/testing\n"
                          "Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n"
                          "MissFile/1.0.2@fenix/stable\n"
                          "NodeInfo/1.0.2@fenix/stable\n"
                          "helloTest/1.4.10@fenix/stable\n", self.client.user_io.out)

    def search_raw(self):
        self.client.run("search Hello* --raw")
        self.assertEquals("Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n"
                          "helloTest/1.4.10@fenix/stable\n", self.client.user_io.out)

    def recipe_pattern_search_test(self):
        self.client.run("search Hello*")
        self.assertEquals("Existing package recipes:\n\n"
                          "Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n"
                          "helloTest/1.4.10@fenix/stable\n", self.client.user_io.out)

        self.client.run("search Hello* --case-sensitive")
        self.assertEquals("Existing package recipes:\n\n"
                          "Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n", self.client.user_io.out)

        self.client.run("search *fenix* --case-sensitive")
        self.assertEquals("Existing package recipes:\n\n"
                          "Bye/0.14@fenix/testing\n"
                          "Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n"
                          "MissFile/1.0.2@fenix/stable\n"
                          "NodeInfo/1.0.2@fenix/stable\n"
                          "helloTest/1.4.10@fenix/stable\n", self.client.user_io.out)

    def package_search_with_invalid_reference_test(self):
        self.client.run("search Hello -q 'a=1'", ignore_error=True)
        self.assertIn("-q parameter only allowed with a valid recipe", str(self.client.user_io.out))

    def package_search_with_empty_query_test(self):
        self.client.run("search Hello/1.4.10/fenix/testing")
        self.assertIn("WindowsPackageSHA", self.client.user_io.out)
        self.assertIn("PlatformIndependantSHA", self.client.user_io.out)
        self.assertIn("LinuxPackageSHA", self.client.user_io.out)

    def package_search_nonescaped_characters_test(self):
        self.client.run('search Hello/1.4.10@fenix/testing -q "compiler=gcc AND compiler.libcxx=libstdc++11"')
        self.assertIn("LinuxPackageSHA", self.client.user_io.out)
        self.assertNotIn("PlatformIndependantSHA", self.client.user_io.out)
        self.assertNotIn("WindowsPackageSHA", self.client.user_io.out)

        self.client.run('search Hello/1.4.10@fenix/testing -q "compiler=gcc AND compiler.libcxx=libstdc++"')
        self.assertNotIn("LinuxPackageSHA", self.client.user_io.out)
        self.assertIn("PlatformIndependantSHA", self.client.user_io.out)
        self.assertNotIn("WindowsPackageSHA", self.client.user_io.out)

        # Now search with a remote
        os.rmdir(self.servers["local"].paths.store)
        shutil.copytree(self.client.paths.store, self.servers["local"].paths.store)
        self.client.run("remove Hello* -f")
        self.client.run('search Hello/1.4.10@fenix/testing -q "compiler=gcc AND compiler.libcxx=libstdc++11" -r local')
        self.assertIn("outdated from recipe: False", self.client.user_io.out)
        self.assertIn("LinuxPackageSHA", self.client.user_io.out)
        self.assertNotIn("PlatformIndependantSHA", self.client.user_io.out)
        self.assertNotIn("WindowsPackageSHA", self.client.user_io.out)

        self.client.run('search Hello/1.4.10@fenix/testing -q "compiler=gcc AND compiler.libcxx=libstdc++" -r local')
        self.assertNotIn("LinuxPackageSHA", self.client.user_io.out)
        self.assertIn("PlatformIndependantSHA", self.client.user_io.out)
        self.assertNotIn("WindowsPackageSHA", self.client.user_io.out)

    def _assert_pkg_q(self, query, packages_found, remote):

        command = 'search Hello/1.4.10@fenix/testing -q \'%s\'' % query
        if remote:
            command += " -r %s" % remote
        self.client.run(command)

        for pack_name in ["LinuxPackageSHA", "PlatformIndependantSHA", "WindowsPackageSHA"]:
            self.assertEquals(pack_name in self.client.user_io.out,
                              pack_name in packages_found, "%s fail" % pack_name)

    def package_search_complex_queries_test(self):

        def test_cases(remote=None):

            if remote:  # Simulate upload to remote
                os.rmdir(self.servers[remote].paths.store)
                shutil.copytree(self.client.paths.store, self.servers[remote].paths.store)

            q = ''
            self._assert_pkg_q(q, ["LinuxPackageSHA", "PlatformIndependantSHA",
                                   "WindowsPackageSHA"], remote)
            q = 'compiler="gcc"'
            self._assert_pkg_q(q, ["LinuxPackageSHA", "PlatformIndependantSHA"], remote)

            q = 'compiler='  # No packages found with empty value
            self._assert_pkg_q(q, [], remote)

            q = 'compiler="gcc" OR compiler.libcxx=libstdc++11'
            # Should find Visual because of the OR, visual doesn't care about libcxx
            self._assert_pkg_q(q, ["LinuxPackageSHA", "PlatformIndependantSHA",
                                   "WindowsPackageSHA"], remote)

            q = '(compiler="gcc" AND compiler.libcxx=libstdc++11) OR compiler.version=4.5'
            self._assert_pkg_q(q, ["LinuxPackageSHA"], remote)

            q = '(compiler="gcc" AND compiler.libcxx=libstdc++11) OR '\
                '(compiler.version=4.5 OR compiler.version=8.1)'
            self._assert_pkg_q(q, ["LinuxPackageSHA", "WindowsPackageSHA"], remote)

            q = '(compiler="gcc" AND compiler.libcxx=libstdc++) OR '\
                '(compiler.version=4.5 OR compiler.version=8.1)'
            self._assert_pkg_q(q, ["LinuxPackageSHA", "PlatformIndependantSHA",
                                   "WindowsPackageSHA"], remote)

            q = '(compiler="gcc" AND compiler.libcxx=libstdc++) OR '\
                '(compiler.version=4.3 OR compiler.version=8.1)'
            self._assert_pkg_q(q, ["PlatformIndependantSHA", "WindowsPackageSHA"], remote)

            q = '(os="Linux" OR os=Windows)'
            self._assert_pkg_q(q, ["PlatformIndependantSHA", "LinuxPackageSHA",
                                   "WindowsPackageSHA"], remote)

            q = '(os="Linux" OR os=Windows) AND use_Qt=True'
            self._assert_pkg_q(q, ["PlatformIndependantSHA",  "WindowsPackageSHA"], remote)

            q = '(os="Linux" OR os=Windows) AND use_Qt=True AND nonexistant_option=3'
            self._assert_pkg_q(q, ["PlatformIndependantSHA",  "WindowsPackageSHA"], remote)

            q = '(os="Linux" OR os=Windows) AND use_Qt=True OR nonexistant_option=3'
            self._assert_pkg_q(q, ["PlatformIndependantSHA",
                                   "WindowsPackageSHA", "LinuxPackageSHA"], remote)

        # test in local
        test_cases()

        # test in remote
        test_cases(remote="local")

        # test in remote with search capabilities
        test_cases(remote="search_able")

    def package_search_with_invalid_query_test(self):
        self.client.run("search Hello/1.4.10/fenix/testing -q 'invalid'", ignore_error=True)
        self.assertIn("Invalid package query: invalid", self.client.user_io.out)

        self.client.run("search Hello/1.4.10/fenix/testing -q 'os= 3'", ignore_error=True)
        self.assertIn("Invalid package query: os= 3", self.client.user_io.out)

        self.client.run("search Hello/1.4.10/fenix/testing -q 'os=3 FAKE '", ignore_error=True)
        self.assertIn("Invalid package query: os=3 FAKE ", self.client.user_io.out)

        self.client.run("search Hello/1.4.10/fenix/testing -q 'os=3 os.compiler=4'", ignore_error=True)
        self.assertIn("Invalid package query: os=3 os.compiler=4", self.client.user_io.out)

        self.client.run("search Hello/1.4.10/fenix/testing -q 'not os=3 AND os.compiler=4'", ignore_error=True)
        self.assertIn("Invalid package query: not os=3 AND os.compiler=4. 'not' operator is not allowed", self.client.user_io.out)

        self.client.run("search Hello/1.4.10/fenix/testing -q 'os=3 AND !os.compiler=4'", ignore_error=True)
        self.assertIn("Invalid package query: os=3 AND !os.compiler=4. '!' character is not allowed", self.client.user_io.out)

    def package_search_properties_filter_test(self):

        # All packages without filter
        self.client.run("search Hello/1.4.10/fenix/testing -q ''")

        self.assertIn("WindowsPackageSHA", self.client.user_io.out)
        self.assertIn("PlatformIndependantSHA", self.client.user_io.out)
        self.assertIn("LinuxPackageSHA", self.client.user_io.out)

        self.client.run('search Hello/1.4.10/fenix/testing -q os=Windows')
        self.assertIn("WindowsPackageSHA", self.client.user_io.out)
        self.assertIn("PlatformIndependantSHA", self.client.user_io.out)
        self.assertNotIn("LinuxPackageSHA", self.client.user_io.out)

        self.client.run('search Hello/1.4.10/fenix/testing -q "os=Windows AND compiler.version=4.5"')
        self.assertIn("There are no packages for reference 'Hello/1.4.10@fenix/testing' matching the query 'os=Windows AND compiler.version=4.5'", self.client.user_io.out)

        self.client.run('search Hello/1.4.10/fenix/testing -q "os=Linux AND compiler.version=4.5"')
        self.assertNotIn("WindowsPackageSHA", self.client.user_io.out)
        self.assertNotIn("PlatformIndependantSHA", self.client.user_io.out)
        self.assertIn("LinuxPackageSHA", self.client.user_io.out)

        self.client.run('search Hello/1.4.10/fenix/testing -q "compiler.version=1.0"')
        self.assertIn("There are no packages for reference 'Hello/1.4.10@fenix/testing' matching the query 'compiler.version=1.0'", self.client.user_io.out)

        self.client.run('search Hello/1.4.10/fenix/testing -q "compiler=gcc AND compiler.version=4.5"')
        self.assertNotIn("WindowsPackageSHA", self.client.user_io.out)
        self.assertNotIn("PlatformIndependantSHA", self.client.user_io.out)
        self.assertIn("LinuxPackageSHA", self.client.user_io.out)

        self.client.run('search Hello/1.4.10/fenix/testing -q "arch=x86"')
        # One package will be outdated from recipe and another don't
        self.assertEquals("""Existing packages for recipe Hello/1.4.10@fenix/testing:

    Package_ID: LinuxPackageSHA
        [options]
            use_Qt: False
        [settings]
            arch: x86
            compiler: gcc
            compiler.libcxx: libstdc++11
            compiler.version: 4.5
            os: Linux
        [requires]
            Hello2/0.1@lasote/stable:11111
            HelloInfo1/0.45@fenix/testing:33333
            OpenSSL/2.10@lasote/testing:2222
        outdated from recipe: False

    Package_ID: PlatformIndependantSHA
        [options]
            use_Qt: True
        [settings]
            arch: x86
            compiler: gcc
            compiler.libcxx: libstdc++
            compiler.version: 4.3
        outdated from recipe: True

""", self.client.user_io.out)

        self.client.run('search helloTest/1.4.10@fenix/stable -q use_OpenGL=False')
        self.assertIn("There are no packages for reference 'helloTest/1.4.10@fenix/stable' "
                      "matching the query 'use_OpenGL=False'", self.client.user_io.out)

        self.client.run('search helloTest/1.4.10@fenix/stable -q use_OpenGL=True')
        self.assertIn("Existing packages for recipe helloTest/1.4.10@fenix/stable", self.client.user_io.out)

        self.client.run('search helloTest/1.4.10@fenix/stable -q "use_OpenGL=True AND arch=x64"')
        self.assertIn("Existing packages for recipe helloTest/1.4.10@fenix/stable", self.client.user_io.out)

        self.client.run('search helloTest/1.4.10@fenix/stable -q "use_OpenGL=True AND arch=x86"')
        self.assertIn("There are no packages for reference 'helloTest/1.4.10@fenix/stable' "
                      "matching the query 'use_OpenGL=True AND arch=x86'", self.client.user_io.out)

    def search_with_no_local_test(self):
        client = TestClient()
        client.run("search nonexist/1.0@lasote/stable")
        self.assertIn("There are no packages", self.client.user_io.out)
