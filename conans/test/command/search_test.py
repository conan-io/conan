import json
import os
import shutil
import unittest

from conans.test.utils.tools import TestClient, TestServer
from conans.paths import PACKAGES_FOLDER, CONANINFO, EXPORT_FOLDER
from conans.model.manifest import FileTreeManifest
from conans import COMPLEX_SEARCH_CAPABILITY
from conans.util.files import load


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
        output = self.client.out
        self.assertIn('There are no packages', output)

        # Conans with and without packages created
        root_folder1 = 'Hello/1.4.10/fenix/testing'
        root_folder2 = 'helloTest/1.4.10/fenix/stable'
        root_folder3 = 'Bye/0.14/fenix/testing'
        root_folder4 = 'NodeInfo/1.0.2/fenix/stable'
        root_folder5 = 'MissFile/1.0.2/fenix/stable'
        root_folder11 = 'Hello/1.4.11/fenix/testing'
        root_folder12 = 'Hello/1.4.12/fenix/testing'

        self.client.save({"Empty/1.10/fake/test/reg/fake.txt": "//",
                          "%s/%s/WindowsPackageSHA/%s" % (root_folder1,
                                                          PACKAGES_FOLDER,
                                                          CONANINFO): conan_vars1,
                          "%s/%s/WindowsPackageSHA/%s" % (root_folder11,
                                                          PACKAGES_FOLDER,
                                                          CONANINFO): conan_vars1,
                          "%s/%s/WindowsPackageSHA/%s" % (root_folder12,
                                                          PACKAGES_FOLDER,
                                                          CONANINFO): conan_vars1,
                          "%s/%s/PlatformIndependantSHA/%s" % (root_folder1,
                                                               PACKAGES_FOLDER,
                                                               CONANINFO): conan_vars1b,
                          "%s/%s/LinuxPackageSHA/%s" % (root_folder1,
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
        fake_manifest.save(os.path.join(self.client.paths.store, root_folder1, EXPORT_FOLDER))
        fake_manifest.save(os.path.join(self.client.paths.store, root_folder2, EXPORT_FOLDER))
        fake_manifest.save(os.path.join(self.client.paths.store, root_folder3, EXPORT_FOLDER))
        fake_manifest.save(os.path.join(self.client.paths.store, root_folder4, EXPORT_FOLDER))
        fake_manifest.save(os.path.join(self.client.paths.store, root_folder5, EXPORT_FOLDER))
        fake_manifest.save(os.path.join(self.client.paths.store, root_folder11, EXPORT_FOLDER))
        fake_manifest.save(os.path.join(self.client.paths.store, root_folder12, EXPORT_FOLDER))

    def recipe_search_all_test(self):
        os.rmdir(self.servers["local"].paths.store)
        shutil.copytree(self.client.paths.store, self.servers["local"].paths.store)
        os.rmdir(self.servers["search_able"].paths.store)
        shutil.copytree(self.client.paths.store, self.servers["search_able"].paths.store)

        def check():
            for remote in ("local", "search_able"):
                expected = """Remote '{}':
Hello/1.4.10@fenix/testing
Hello/1.4.11@fenix/testing
Hello/1.4.12@fenix/testing
helloTest/1.4.10@fenix/stable""".format(remote)
                self.assertIn(expected, self.client.out)

        self.client.run("search Hello* -r=all")
        check()

        self.client.run("search Hello* -r=all --raw")
        check()

    def recipe_search_test(self):
        self.client.run("search Hello*")
        self.assertEquals("Existing package recipes:\n\n"
                          "Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n"
                          "helloTest/1.4.10@fenix/stable\n", self.client.out)

        self.client.run("search Hello* --case-sensitive")
        self.assertEquals("Existing package recipes:\n\n"
                          "Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n",
                          self.client.out)

        self.client.run("search *fenix* --case-sensitive")
        self.assertEquals("Existing package recipes:\n\n"
                          "Bye/0.14@fenix/testing\n"
                          "Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n"
                          "MissFile/1.0.2@fenix/stable\n"
                          "NodeInfo/1.0.2@fenix/stable\n"
                          "helloTest/1.4.10@fenix/stable\n", self.client.out)

        self.client.run("search Hello/*@fenix/testing")
        self.assertIn("Hello/1.4.10@fenix/testing\n"
                      "Hello/1.4.11@fenix/testing\n"
                      "Hello/1.4.12@fenix/testing\n", self.client.out)

    def search_partial_match_test(self):
        self.client.run("search Hello")
        self.assertEquals("Existing package recipes:\n\n"
                          "Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n", self.client.out)

        self.client.run("search hello")
        self.assertEquals("Existing package recipes:\n\n"
                          "Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n", self.client.out)

        self.client.run("search Hello --case-sensitive")
        self.assertEquals("Existing package recipes:\n\n"
                          "Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n", self.client.out)

        self.client.run("search Hel")
        self.assertEquals("There are no packages matching the 'Hel' pattern\n", self.client.out)

        self.client.run("search Hello/")
        self.assertEquals("Existing package recipes:\n\n"
                          "Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n", self.client.out)

        self.client.run("search Hello/1.4.10")
        self.assertEquals("Existing package recipes:\n\n"
                          "Hello/1.4.10@fenix/testing\n", self.client.out)

        self.client.run("search Hello/1.4")
        self.assertEquals("There are no packages matching the 'Hello/1.4' pattern\n", self.client.out)

        self.client.run("search Hello/1.4.10@")
        self.assertEquals("Existing package recipes:\n\n"
                          "Hello/1.4.10@fenix/testing\n", self.client.out)

        self.client.run("search Hello/1.4.10@fenix")
        self.assertEquals("Existing package recipes:\n\n"
                          "Hello/1.4.10@fenix/testing\n", self.client.out)

        self.client.run("search Hello/1.4.10@fen")
        self.assertEquals("There are no packages matching the 'Hello/1.4.10@fen' pattern\n", self.client.out)

        self.client.run("search Hello/1.4.10@fenix/")
        self.assertEquals("Existing package recipes:\n\n"
                          "Hello/1.4.10@fenix/testing\n", self.client.out)

        error = self.client.run("search Hello/1.4.10@fenix/test", ignore_error=True)
        self.assertTrue(error)
        self.assertEquals("ERROR: Recipe not found: Hello/1.4.10@fenix/test\n", self.client.out)

    def search_raw_test(self):
        self.client.run("search Hello* --raw")
        self.assertEquals("Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n"
                          "helloTest/1.4.10@fenix/stable\n", self.client.out)

    def search_html_table_test(self):
        self.client.run("search Hello/1.4.10/fenix/testing --table=table.html")
        html = load(os.path.join(self.client.current_folder, "table.html"))
        self.assertIn("<h1>Hello/1.4.10@fenix/testing</h1>", html)
        self.assertIn("<td>Linux gcc 4.5 (libstdc++11)</td>", html)
        self.assertIn("<td>Windows Visual Studio 8.1</td>", html)

    def search_html_table_all_test(self):
        os.rmdir(self.servers["local"].paths.store)
        shutil.copytree(self.client.paths.store, self.servers["local"].paths.store)
        os.rmdir(self.servers["search_able"].paths.store)
        shutil.copytree(self.client.paths.store, self.servers["search_able"].paths.store)

        self.client.run("search Hello/1.4.10/fenix/testing -r=all --table=table.html")
        html = load(os.path.join(self.client.current_folder, "table.html"))

        self.assertIn("<h1>Hello/1.4.10@fenix/testing</h1>", html)
        self.assertIn("<h2>'local':</h2>", html)
        self.assertIn("<h2>'search_able':</h2>", html)

        self.assertEqual(html.count("<td>Linux gcc 4.5 (libstdc++11)</td>"), 2)
        self.assertEqual(html.count("<td>Windows Visual Studio 8.1</td>"), 2)

    def search_html_table_with_no_reference_test(self):
        self.client.run("search Hello* --table=table.html", ignore_error=True)
        self.assertIn("ERROR: '--table' argument can only be used with a reference",
                      self.client.out)

    def recipe_pattern_search_test(self):
        self.client.run("search Hello*")
        self.assertEquals("Existing package recipes:\n\n"
                          "Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n"
                          "helloTest/1.4.10@fenix/stable\n", self.client.out)

        self.client.run("search Hello* --case-sensitive")
        self.assertEquals("Existing package recipes:\n\n"
                          "Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n", self.client.out)

        self.client.run("search *fenix* --case-sensitive")
        self.assertEquals("Existing package recipes:\n\n"
                          "Bye/0.14@fenix/testing\n"
                          "Hello/1.4.10@fenix/testing\n"
                          "Hello/1.4.11@fenix/testing\n"
                          "Hello/1.4.12@fenix/testing\n"
                          "MissFile/1.0.2@fenix/stable\n"
                          "NodeInfo/1.0.2@fenix/stable\n"
                          "helloTest/1.4.10@fenix/stable\n", self.client.out)

    def package_search_with_invalid_reference_test(self):
        self.client.run("search Hello -q 'a=1'", ignore_error=True)
        self.assertIn("-q parameter only allowed with a valid recipe", str(self.client.out))

    def package_search_with_empty_query_test(self):
        self.client.run("search Hello/1.4.10/fenix/testing")
        self.assertIn("WindowsPackageSHA", self.client.out)
        self.assertIn("PlatformIndependantSHA", self.client.out)
        self.assertIn("LinuxPackageSHA", self.client.out)

    def package_search_nonescaped_characters_test(self):
        self.client.run('search Hello/1.4.10@fenix/testing -q "compiler=gcc AND compiler.libcxx=libstdc++11"')
        self.assertIn("LinuxPackageSHA", self.client.out)
        self.assertNotIn("PlatformIndependantSHA", self.client.out)
        self.assertNotIn("WindowsPackageSHA", self.client.out)

        self.client.run('search Hello/1.4.10@fenix/testing -q "compiler=gcc AND compiler.libcxx=libstdc++"')
        self.assertNotIn("LinuxPackageSHA", self.client.out)
        self.assertIn("PlatformIndependantSHA", self.client.out)
        self.assertNotIn("WindowsPackageSHA", self.client.out)

        # Now search with a remote
        os.rmdir(self.servers["local"].paths.store)
        shutil.copytree(self.client.paths.store, self.servers["local"].paths.store)

        self.client.run('search Hello/1.4.10@fenix/testing -q "compiler=gcc AND compiler.libcxx=libstdc++11" -r local')
        self.assertIn("Outdated from recipe: False", self.client.out)
        self.assertIn("LinuxPackageSHA", self.client.out)
        self.assertNotIn("PlatformIndependantSHA", self.client.out)
        self.assertNotIn("WindowsPackageSHA", self.client.out)

        self.client.run('search Hello/1.4.10@fenix/testing -q "compiler=gcc AND compiler.libcxx=libstdc++" -r local')
        self.assertNotIn("LinuxPackageSHA", self.client.out)
        self.assertIn("PlatformIndependantSHA", self.client.out)
        self.assertNotIn("WindowsPackageSHA", self.client.out)

        # Now search in all remotes
        os.rmdir(self.servers["search_able"].paths.store)
        shutil.copytree(self.client.paths.store, self.servers["search_able"].paths.store)

        self.client.run('search Hello/1.4.10@fenix/testing -q "compiler=gcc AND compiler.libcxx=libstdc++11" -r all')
        self.assertEqual(str(self.client.out).count("Outdated from recipe: False"), 2)
        self.assertEqual(str(self.client.out).count("LinuxPackageSHA"), 2)
        self.assertNotIn("PlatformIndependantSHA", self.client.out)
        self.assertNotIn("WindowsPackageSHA", self.client.out)

        self.client.run('search Hello/1.4.10@fenix/testing -q "compiler=gcc AND compiler.libcxx=libstdc++" -r all')
        self.assertNotIn("LinuxPackageSHA", self.client.out)
        self.assertEqual(str(self.client.out).count("PlatformIndependantSHA"), 2)
        self.assertNotIn("WindowsPackageSHA", self.client.out)

    def _assert_pkg_q(self, query, packages_found, remote):

        command = 'search Hello/1.4.10@fenix/testing -q \'%s\'' % query
        if remote:
            command += " -r %s" % remote
        self.client.run(command)

        for pack_name in ["LinuxPackageSHA", "PlatformIndependantSHA", "WindowsPackageSHA"]:
            self.assertEquals(pack_name in self.client.out,
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
            self._assert_pkg_q(q, ["LinuxPackageSHA", "PlatformIndependantSHA"], remote)

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
            self._assert_pkg_q(q, ["LinuxPackageSHA", "WindowsPackageSHA"], remote)

            q = '(os="Linux" OR os=None)'
            self._assert_pkg_q(q, ["LinuxPackageSHA", "PlatformIndependantSHA"], remote)

            q = '(os=None)'
            self._assert_pkg_q(q, ["PlatformIndependantSHA"], remote)

            q = '(os="Linux" OR os=Windows) AND use_Qt=True'
            self._assert_pkg_q(q, ["WindowsPackageSHA"], remote)

            q = '(os=None OR os=Windows) AND use_Qt=True'
            self._assert_pkg_q(q, ["PlatformIndependantSHA", "WindowsPackageSHA"], remote)

            q = '(os="Linux" OR os=Windows) AND use_Qt=True AND nonexistant_option=3'
            self._assert_pkg_q(q, [], remote)

            q = '(os="Linux" OR os=Windows) AND use_Qt=True OR nonexistant_option=3'
            self._assert_pkg_q(q, ["WindowsPackageSHA", "LinuxPackageSHA"], remote)

        # test in local
        test_cases()

        # test in remote
        test_cases(remote="local")

        # test in remote with search capabilities
        test_cases(remote="search_able")

    def package_search_all_remotes_test(self):
        os.rmdir(self.servers["local"].paths.store)
        shutil.copytree(self.client.paths.store, self.servers["local"].paths.store)
        os.rmdir(self.servers["search_able"].paths.store)
        shutil.copytree(self.client.paths.store, self.servers["search_able"].paths.store)

        self.client.run("search Hello/1.4.10/fenix/testing -r=all")
        self.assertIn("Existing recipe in remote 'local':", self.client.out)
        self.assertIn("Existing recipe in remote 'search_able':", self.client.out)

        self.assertEqual(str(self.client.out).count("WindowsPackageSHA"), 2)
        self.assertEqual(str(self.client.out).count("PlatformIndependantSHA"), 2)
        self.assertEqual(str(self.client.out).count("LinuxPackageSHA"), 2)

    def package_search_with_invalid_query_test(self):
        self.client.run("search Hello/1.4.10/fenix/testing -q 'invalid'", ignore_error=True)
        self.assertIn("Invalid package query: invalid", self.client.out)

        self.client.run("search Hello/1.4.10/fenix/testing -q 'os= 3'", ignore_error=True)
        self.assertIn("Invalid package query: os= 3", self.client.out)

        self.client.run("search Hello/1.4.10/fenix/testing -q 'os=3 FAKE '", ignore_error=True)
        self.assertIn("Invalid package query: os=3 FAKE ", self.client.out)

        self.client.run("search Hello/1.4.10/fenix/testing -q 'os=3 os.compiler=4'", ignore_error=True)
        self.assertIn("Invalid package query: os=3 os.compiler=4", self.client.out)

        self.client.run("search Hello/1.4.10/fenix/testing -q 'not os=3 AND os.compiler=4'", ignore_error=True)
        self.assertIn("Invalid package query: not os=3 AND os.compiler=4. 'not' operator is not allowed",
                      self.client.out)

        self.client.run("search Hello/1.4.10/fenix/testing -q 'os=3 AND !os.compiler=4'", ignore_error=True)
        self.assertIn("Invalid package query: os=3 AND !os.compiler=4. '!' character is not allowed", self.client.out)

    def package_search_properties_filter_test(self):

        # All packages without filter
        self.client.run("search Hello/1.4.10/fenix/testing -q ''")

        self.assertIn("WindowsPackageSHA", self.client.out)
        self.assertIn("PlatformIndependantSHA", self.client.out)
        self.assertIn("LinuxPackageSHA", self.client.out)

        self.client.run('search Hello/1.4.10/fenix/testing -q os=Windows')
        self.assertIn("WindowsPackageSHA", self.client.out)
        self.assertNotIn("PlatformIndependantSHA", self.client.out)
        self.assertNotIn("LinuxPackageSHA", self.client.out)

        self.client.run('search Hello/1.4.10/fenix/testing -q "os=Windows or os=None"')
        self.assertIn("WindowsPackageSHA", self.client.out)
        self.assertIn("PlatformIndependantSHA", self.client.out)
        self.assertNotIn("LinuxPackageSHA", self.client.out)

        self.client.run('search Hello/1.4.10/fenix/testing -q "os=Windows or os=Linux"')
        self.assertIn("WindowsPackageSHA", self.client.out)
        self.assertNotIn("PlatformIndependantSHA", self.client.out)
        self.assertIn("LinuxPackageSHA", self.client.out)

        self.client.run('search Hello/1.4.10/fenix/testing -q "os=Windows AND compiler.version=4.5"')
        self.assertIn("There are no packages for reference 'Hello/1.4.10@fenix/testing' "
                      "matching the query 'os=Windows AND compiler.version=4.5'", self.client.out)

        self.client.run('search Hello/1.4.10/fenix/testing -q "os=Linux AND compiler.version=4.5"')
        self.assertNotIn("WindowsPackageSHA", self.client.out)
        self.assertNotIn("PlatformIndependantSHA", self.client.out)
        self.assertIn("LinuxPackageSHA", self.client.out)

        self.client.run('search Hello/1.4.10/fenix/testing -q "compiler.version=1.0"')
        self.assertIn("There are no packages for reference 'Hello/1.4.10@fenix/testing' "
                      "matching the query 'compiler.version=1.0'", self.client.out)

        self.client.run('search Hello/1.4.10/fenix/testing -q "compiler=gcc AND compiler.version=4.5"')
        self.assertNotIn("WindowsPackageSHA", self.client.out)
        self.assertNotIn("PlatformIndependantSHA", self.client.out)
        self.assertIn("LinuxPackageSHA", self.client.out)

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
        Outdated from recipe: False

    Package_ID: PlatformIndependantSHA
        [options]
            use_Qt: True
        [settings]
            arch: x86
            compiler: gcc
            compiler.libcxx: libstdc++
            compiler.version: 4.3
        Outdated from recipe: True

""", self.client.out)

        self.client.run('search helloTest/1.4.10@fenix/stable -q use_OpenGL=False')
        self.assertIn("There are no packages for reference 'helloTest/1.4.10@fenix/stable' "
                      "matching the query 'use_OpenGL=False'", self.client.out)

        self.client.run('search helloTest/1.4.10@fenix/stable -q use_OpenGL=True')
        self.assertIn("Existing packages for recipe helloTest/1.4.10@fenix/stable", self.client.out)

        self.client.run('search helloTest/1.4.10@fenix/stable -q "use_OpenGL=True AND arch=x64"')
        self.assertIn("Existing packages for recipe helloTest/1.4.10@fenix/stable", self.client.out)

        self.client.run('search helloTest/1.4.10@fenix/stable -q "use_OpenGL=True AND arch=x86"')
        self.assertIn("There are no packages for reference 'helloTest/1.4.10@fenix/stable' "
                      "matching the query 'use_OpenGL=True AND arch=x86'", self.client.out)

    def search_with_no_local_test(self):
        client = TestClient()
        error = client.run("search nonexist/1.0@lasote/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Recipe not found: nonexist/1.0@lasote/stable", client.out)

    def search_with_no_registry_test(self):
        # https://github.com/conan-io/conan/issues/2589
        client = TestClient()
        os.remove(os.path.join(client.client_cache.registry))
        error = client.run("search nonexist/1.0@lasote/stable -r=myremote", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("WARN: Remotes registry file missing, creating default one", client.out)
        self.assertIn("ERROR: No remote 'myremote' defined in remotes", client.out)

    def search_json_test(self):
        # Test invalid arguments
        error = self.client.run("search h* -r all --json search.json --table table.html",
                                ignore_error=True)
        self.assertTrue(error)
        self.assertIn("'--table' argument cannot be used together with '--json'", self.client.out)
        json_path = os.path.join(self.client.current_folder, "search.json")
        self.assertFalse(os.path.exists(json_path))

        # Test search packages for unknown reference
        error = self.client.run("search fake/0.1@danimtb/testing --json search.json",
                                ignore_error=True)
        self.assertTrue(error)
        json_path = os.path.join(self.client.current_folder, "search.json")
        self.assertTrue(os.path.exists(json_path))
        json_content = load(json_path)
        output = json.loads(json_content)
        self.assertTrue(output["error"])
        self.assertEqual(0, len(output["results"]))

        # Test search recipes local
        self.client.run("search Hello* --json search.json")
        self.assertTrue(os.path.exists(json_path))
        json_content = load(json_path)
        output = json.loads(json_content)
        expected_output = {
            'error': False,
            'results': [
                {
                    'remote': None,
                    'items': [
                        {
                            'recipe': {
                                'id': 'Hello/1.4.10@fenix/testing'}
                        },
                        {
                            'recipe': {
                                'id': 'Hello/1.4.11@fenix/testing'}
                        },
                        {
                            'recipe': {
                                'id': 'Hello/1.4.12@fenix/testing'}
                        },
                        {
                            'recipe': {
                                'id': 'helloTest/1.4.10@fenix/stable'}
                        }
                    ]
                }
            ]
        }
        self.assertEqual(expected_output, output)

        # Test search recipes all remotes
        os.rmdir(self.servers["local"].paths.store)
        shutil.copytree(self.client.paths.store, self.servers["local"].paths.store)
        os.rmdir(self.servers["search_able"].paths.store)
        shutil.copytree(self.client.paths.store, self.servers["search_able"].paths.store)

        self.client.run("search Hello* -r=all --json search.json")
        self.assertTrue(os.path.exists(json_path))
        json_content = load(json_path)
        output = json.loads(json_content)
        expected_output = {
            'error': False,
            'results': [
                {
                    'remote': 'local',
                    'items': [
                        {
                             'recipe': {
                                 'id': 'Hello/1.4.10@fenix/testing'}
                        },
                        {
                             'recipe': {
                                 'id': 'Hello/1.4.11@fenix/testing'}
                        },
                        {
                             'recipe': {
                                 'id': 'Hello/1.4.12@fenix/testing'}
                        },
                        {
                             'recipe': {
                                 'id': 'helloTest/1.4.10@fenix/stable'}
                        }
                    ]
                },
                {
                    'remote': 'search_able',
                    'items': [
                        {
                            'recipe': {
                                'id': 'Hello/1.4.10@fenix/testing'}
                        },
                        {
                            'recipe': {
                                'id': 'Hello/1.4.11@fenix/testing'}
                        },
                        {
                            'recipe': {
                                'id': 'Hello/1.4.12@fenix/testing'}
                        },
                        {
                            'recipe': {
                                'id': 'helloTest/1.4.10@fenix/stable'}
                        }
                    ]
                }
            ]
        }
        self.assertEqual(expected_output, output)

        # Test search recipe remote
        self.client.run("search Hello* -r=local --json search.json")
        self.assertTrue(os.path.exists(json_path))
        json_content = load(json_path)
        output = json.loads(json_content)
        expected_output = {
            'error': False,
            'results': [
                {
                    'remote': 'local',
                    'items': [
                        {
                            'recipe': {
                                'id': 'Hello/1.4.10@fenix/testing'}
                        },
                        {
                            'recipe': {
                                'id': 'Hello/1.4.11@fenix/testing'}
                        },
                        {
                            'recipe': {
                                'id': 'Hello/1.4.12@fenix/testing'}
                        },
                        {
                            'recipe': {
                                'id': 'helloTest/1.4.10@fenix/stable'}
                        }
                    ]
                }
            ]
        }
        self.assertEqual(expected_output, output)

        # Test search packages local
        self.client.run("search Hello/1.4.10@fenix/testing --json search.json")
        self.assertTrue(os.path.exists(json_path))
        json_content = load(json_path)
        output = json.loads(json_content)
        expected_output = {
            'error': False,
            'results': [
                {
                    'remote': None,
                    'items': [
                        {
                            'recipe': {
                                'id': 'Hello/1.4.10@fenix/testing'},
                            'packages': [
                                {
                                    'id': 'LinuxPackageSHA',
                                    'options': {
                                        'use_Qt': 'False'},
                                    'settings': {
                                        'arch': 'x86',
                                        'compiler': 'gcc',
                                        'compiler.libcxx': 'libstdc++11',
                                        'compiler.version': '4.5',
                                        'os': 'Linux'},
                                    'requires': [
                                        'Hello2/0.1@lasote/stable:11111',
                                        'HelloInfo1/0.45@fenix/testing:33333',
                                        'OpenSSL/2.10@lasote/testing:2222'],
                                    'outdated': False
                                },
                                {
                                    'id': 'PlatformIndependantSHA',
                                    'options': {
                                        'use_Qt': 'True'},
                                    'settings': {
                                        'arch': 'x86',
                                        'compiler': 'gcc',
                                        'compiler.libcxx': 'libstdc++',
                                        'compiler.version': '4.3'},
                                    'requires': [],
                                    'outdated': True
                                },
                                {
                                    'id': 'WindowsPackageSHA',
                                    'options': {
                                        'use_Qt': 'True'},
                                    'settings': {
                                        'arch': 'x64',
                                        'compiler': 'Visual Studio',
                                        'compiler.version': '8.1',
                                        'os': 'Windows'},
                                    'requires': [
                                        'Hello2/0.1@lasote/stable:11111',
                                        'HelloInfo1/0.45@fenix/testing:33333',
                                        'OpenSSL/2.10@lasote/testing:2222'],
                                    'outdated': True
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        self.assertEqual(expected_output, output)

        # Test search packages remote
        self.client.run("search Hello/1.4.10@fenix/testing -r search_able --json search.json")
        self.assertTrue(os.path.exists(json_path))
        json_content = load(json_path)
        output = json.loads(json_content)
        expected_output = {
            'error': False,
            'results': [
                {
                    'remote': 'search_able',
                    'items': [
                        {
                            'recipe': {
                                'id': 'Hello/1.4.10@fenix/testing'},
                            'packages': [
                                {
                                    'id': 'LinuxPackageSHA',
                                    'options': {
                                        'use_Qt': 'False'},
                                    'settings': {
                                        'arch': 'x86',
                                        'compiler': 'gcc',
                                        'compiler.libcxx': 'libstdc++11',
                                        'compiler.version': '4.5',
                                        'os': 'Linux'},
                                    'requires': [
                                        'Hello2/0.1@lasote/stable:11111',
                                        'HelloInfo1/0.45@fenix/testing:33333',
                                        'OpenSSL/2.10@lasote/testing:2222'],
                                    'outdated': False
                                },
                                {
                                    'id': 'PlatformIndependantSHA',
                                    'options': {
                                        'use_Qt': 'True'},
                                    'settings': {
                                        'arch': 'x86',
                                        'compiler': 'gcc',
                                        'compiler.libcxx': 'libstdc++',
                                        'compiler.version': '4.3'},
                                    'requires': [],
                                    'outdated': True
                                },
                                {
                                    'id': 'WindowsPackageSHA',
                                    'options': {
                                        'use_Qt': 'True'},
                                    'settings': {
                                        'arch': 'x64',
                                        'compiler': 'Visual Studio',
                                        'compiler.version': '8.1',
                                        'os': 'Windows'},
                                    'requires': [
                                        'Hello2/0.1@lasote/stable:11111',
                                        'HelloInfo1/0.45@fenix/testing:33333',
                                        'OpenSSL/2.10@lasote/testing:2222'],
                                    'outdated': True
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        self.assertEqual(expected_output, output)

        # Test search packages remote ALL
        self.client.run("search Hello/1.4.10@fenix/testing -r all --json search.json")
        self.assertTrue(os.path.exists(json_path))
        json_content = load(json_path)
        output = json.loads(json_content)
        expected_output = {
            'error': False,
            'results': [
                {
                    'remote': 'local',
                    'items': [
                        {
                            'recipe': {
                                'id': 'Hello/1.4.10@fenix/testing'},
                            'packages': [
                                {
                                    'id': 'LinuxPackageSHA',
                                    'options': {
                                        'use_Qt': 'False'},
                                    'settings': {
                                        'arch': 'x86',
                                        'compiler': 'gcc',
                                        'compiler.libcxx': 'libstdc++11',
                                        'compiler.version': '4.5',
                                        'os': 'Linux'},
                                    'requires': [
                                        'Hello2/0.1@lasote/stable:11111',
                                        'HelloInfo1/0.45@fenix/testing:33333',
                                        'OpenSSL/2.10@lasote/testing:2222'],
                                    'outdated': False
                                },
                                {
                                    'id': 'PlatformIndependantSHA',
                                    'options': {
                                        'use_Qt': 'True'},
                                    'settings': {
                                        'arch': 'x86',
                                        'compiler': 'gcc',
                                        'compiler.libcxx': 'libstdc++',
                                        'compiler.version': '4.3'},
                                    'requires': [],
                                    'outdated': True
                                },
                                {
                                    'id': 'WindowsPackageSHA',
                                    'options': {
                                        'use_Qt': 'True'},
                                    'settings': {
                                        'arch': 'x64',
                                        'compiler': 'Visual Studio',
                                        'compiler.version': '8.1',
                                        'os': 'Windows'},
                                    'requires': [
                                        'Hello2/0.1@lasote/stable:11111',
                                        'HelloInfo1/0.45@fenix/testing:33333',
                                        'OpenSSL/2.10@lasote/testing:2222'],
                                    'outdated': True
                                }
                            ]
                        }
                    ]
                },
                {
                    'remote': 'search_able',
                    'items': [
                        {
                            'recipe': {
                                'id': 'Hello/1.4.10@fenix/testing'},
                            'packages': [
                                {
                                    'id': 'LinuxPackageSHA',
                                    'options': {
                                        'use_Qt': 'False'},
                                    'settings': {
                                        'arch': 'x86',
                                        'compiler': 'gcc',
                                        'compiler.libcxx': 'libstdc++11',
                                        'compiler.version': '4.5',
                                        'os': 'Linux'},
                                    'requires': [
                                        'Hello2/0.1@lasote/stable:11111',
                                        'HelloInfo1/0.45@fenix/testing:33333',
                                        'OpenSSL/2.10@lasote/testing:2222'],
                                    'outdated': False
                                },
                                {
                                    'id': 'PlatformIndependantSHA',
                                    'options': {
                                        'use_Qt': 'True'},
                                    'settings': {
                                        'arch': 'x86',
                                        'compiler': 'gcc',
                                        'compiler.libcxx': 'libstdc++',
                                        'compiler.version': '4.3'},
                                    'requires': [],
                                    'outdated': True
                                },
                                {
                                    'id': 'WindowsPackageSHA',
                                    'options': {
                                        'use_Qt': 'True'},
                                    'settings': {
                                        'arch': 'x64',
                                        'compiler': 'Visual Studio',
                                        'compiler.version': '8.1',
                                        'os': 'Windows'},
                                    'requires': [
                                        'Hello2/0.1@lasote/stable:11111',
                                        'HelloInfo1/0.45@fenix/testing:33333',
                                        'OpenSSL/2.10@lasote/testing:2222'],
                                    'outdated': True
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        self.assertEqual(expected_output, output)

    def search_packages_with_reference_not_exported_test(self):
        error = self.client.run("search my_pkg/1.0@conan/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Recipe not found: my_pkg/1.0@conan/stable", self.client.out)

    def initial_search_without_registry_test(self):
        client = TestClient()
        os.remove(client.client_cache.registry)
        client.run("search my_pkg")
        self.assertIn("WARN: Remotes registry file missing, creating default one", client.out)
        self.assertIn("There are no packages matching the 'my_pkg' pattern", client.out)


class SearchOutdatedTest(unittest.TestCase):
    def search_outdated_test(self):
        test_server = TestServer(users={"lasote": "password"})  # exported users and passwords
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "password")]})
        conanfile = """from conans import ConanFile
class Test(ConanFile):
    name = "Test"
    version = "0.1"
    settings = "os"
    """
        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/testing")
        client.run("install Test/0.1@lasote/testing --build -s os=Windows")
        client.save({"conanfile.py": "# comment\n%s" % conanfile})
        client.run("export . lasote/testing")
        client.run("install Test/0.1@lasote/testing --build -s os=Linux")
        client.run("upload * --all --confirm")
        for remote in ("", "-r=default"):
            client.run("search Test/0.1@lasote/testing %s" % remote)
            self.assertIn("os: Windows", client.user_io.out)
            self.assertIn("os: Linux", client.user_io.out)
            client.run("search Test/0.1@lasote/testing  %s --outdated" % remote)
            self.assertIn("os: Windows", client.user_io.out)
            self.assertNotIn("os: Linux", client.user_io.out)
