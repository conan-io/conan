import json
import os
import sys
import textwrap
import unittest

from mock import patch, PropertyMock

from conans.model.graph_lock import LOCKFILE
from conans.build_info.command import run
from conans.test.utils.tools import TestClient


class MyBuildInfoCreation(unittest.TestCase):
    @patch('conans.client.cache.cache.ClientCache.put_headers_path', new_callable=PropertyMock)
    def test_build_info_start(self, mock_put_headers_path):
        client = TestClient()
        props_file = client.cache.put_headers_path
        sys.argv = ['conan_build_info', 'start', 'MyBuildName', '42']
        mock_put_headers_path.return_value = props_file
        run()
        with open(props_file) as f:
            content = f.read()
            self.assertIn('MyBuildName', content)
            self.assertIn('42', content)

    @patch('conans.client.cache.cache.ClientCache.put_headers_path', new_callable=PropertyMock)
    def test_build_info_stop(self, mock_put_headers_path):
        client = TestClient()
        props_file = client.cache.put_headers_path
        sys.argv = ['conan_build_info', 'stop']
        mock_put_headers_path.return_value = client.cache.put_headers_path
        run()
        with open(props_file) as f:
            content = f.read()
            self.assertEqual('', content)

    def test_build_info_create(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, load
            import os
            class Pkg(ConanFile):
                {requires}
                exports_sources = "myfile.txt"
                keep_imports = True
                def imports(self):
                    self.copy("myfile.txt", folder=True)
                def package(self):
                    self.copy("*myfile.txt")
                def package_info(self):
                    self.output.info("SELF FILE: %s"
                        % load(os.path.join(self.package_folder, "myfile.txt")))
                    for d in os.listdir(self.package_folder):
                        p = os.path.join(self.package_folder, d, "myfile.txt")
                        if os.path.isfile(p):
                            self.output.info("DEP FILE %s: %s" % (d, load(p)))
                """)
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile.format(requires=""),
                     "myfile.txt": "HelloA"})
        client.run("create . PkgA/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgA/0.1@user/channel"'),
            "myfile.txt": "HelloB"})
        client.run("create . PkgB/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgB/0.1@user/channel"'),
            "myfile.txt": "HelloC"})
        client.run("create . PkgC/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgC/0.1@user/channel"'),
            "myfile.txt": "HelloD"})
        client.run("create . PkgD/0.1@user/channel")
        client.run("graph lock PkgD/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgA/0.1@user/channel"'),
            "myfile.txt": "HelloB"})
        client.run("create . PkgB/0.2@user/testing --lockfile")
        registry = client.cache.registry
        headers_path = client.cache.put_headers_path
        client.run("upload * --all --confirm")

        @patch('conans.client.cache.cache.ClientCache.put_headers_path', new_callable=PropertyMock)
        @patch('conans.client.cache.cache.ClientCache.registry', new_callable=PropertyMock)
        @patch('conans.client.cache.cache.ClientCache.package_layout',
               new=client.cache.package_layout)
        @patch('conans.client.cache.cache.ClientCache.read_put_headers',
               new=client.cache.read_put_headers)
        def create(registry_mock, mock_put_headers_path):
            registry_mock.return_value = registry
            mock_put_headers_path.return_value = headers_path
            sys.argv = ['conan_build_info', 'start', 'MyBuildName', '42']
            run()
            sys.argv = ['conan_build_info', 'create',
                        os.path.join(client.current_folder, 'buildinfo.json'), '--lockfile',
                        os.path.join(client.current_folder, LOCKFILE)]
            run()

        create()
        with open(os.path.join(client.current_folder, 'buildinfo.json')) as f:
            buildinfo = json.load(f)
            self.assertEqual(buildinfo["modules"][0]["id"], "PkgB/0.2@user/testing")
            self.assertEqual(buildinfo["modules"][1]["id"],
                             "PkgB/0.2@user/testing:5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5")
            self.assertEqual(buildinfo["modules"][0]["artifacts"][0]["name"], "conan_sources.tgz")
            self.assertEqual(buildinfo["modules"][1]["artifacts"][0]["name"], "conan_package.tgz")

    def test_build_info_update(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, load
            import os
            class Pkg(ConanFile):
                {requires}
                exports_sources = "myfile.txt"
                keep_imports = True
                def imports(self):
                    self.copy("myfile.txt", folder=True)
                def package(self):
                    self.copy("*myfile.txt")
                def package_info(self):
                    self.output.info("SELF FILE: %s"
                        % load(os.path.join(self.package_folder, "myfile.txt")))
                    for d in os.listdir(self.package_folder):
                        p = os.path.join(self.package_folder, d, "myfile.txt")
                        if os.path.isfile(p):
                            self.output.info("DEP FILE %s: %s" % (d, load(p)))
                """)
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile.format(requires=""),
                     "myfile.txt": "HelloA"})
        client.run("create . PkgA/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgA/0.1@user/channel"'),
            "myfile.txt": "HelloB"})
        client.run("create . PkgB/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgB/0.1@user/channel"'),
            "myfile.txt": "HelloC"})
        client.run("create . PkgC/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgC/0.1@user/channel"'),
            "myfile.txt": "HelloD"})
        client.run("create . PkgD/0.1@user/channel")
        client.run("graph lock PkgD/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgA/0.1@user/channel"'),
            "myfile.txt": "HelloB"})
        client.run("create . PkgB/0.2@user/testing --lockfile")
        registry = client.cache.registry
        headers_path = client.cache.put_headers_path
        client.run("upload * --all --confirm")

        @patch('conans.client.cache.cache.ClientCache.put_headers_path', new_callable=PropertyMock)
        @patch('conans.client.cache.cache.ClientCache.registry', new_callable=PropertyMock)
        @patch('conans.client.cache.cache.ClientCache.package_layout',
               new=client.cache.package_layout)
        @patch('conans.client.cache.cache.ClientCache.read_put_headers',
               new=client.cache.read_put_headers)
        def create_bi_a(registry_mock, mock_put_headers_path):
            registry_mock.return_value = registry
            mock_put_headers_path.return_value = headers_path
            sys.argv = ['conan_build_info', 'start', 'MyBuildName', '42']
            run()
            sys.argv = ['conan_build_info', 'create',
                        os.path.join(client.current_folder, 'buildinfo_a.json'), '--lockfile',
                        os.path.join(client.current_folder, LOCKFILE),
                        '--user', 'user', '--password', 'password']
            run()

        create_bi_a()

        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgB/0.2@user/channel"'),
            "myfile.txt": "HelloC"})
        client.run("create . PkgC/0.2@user/testing --lockfile")
        client.run("upload * --all --confirm")

        @patch('conans.client.cache.cache.ClientCache.put_headers_path', new_callable=PropertyMock)
        @patch('conans.client.cache.cache.ClientCache.registry', new_callable=PropertyMock)
        @patch('conans.client.cache.cache.ClientCache.package_layout',
               new=client.cache.package_layout)
        @patch('conans.client.cache.cache.ClientCache.read_put_headers',
               new=client.cache.read_put_headers)
        def create_bi_b(registry_mock, mock_put_headers_path):
            registry_mock.return_value = registry
            mock_put_headers_path.return_value = headers_path
            sys.argv = ['conan_build_info', 'start', 'MyBuildName', '43']
            run()
            sys.argv = ['conan_build_info', 'create',
                        os.path.join(client.current_folder, 'buildinfo_b.json'), '--lockfile',
                        os.path.join(client.current_folder, LOCKFILE),
                        '--user', 'user', '--password', 'password']
            run()

        create_bi_b()

        with open(os.path.join(client.current_folder, 'buildinfo_a.json')) as f:
            buildinfo = json.load(f)
            print(buildinfo)

        with open(os.path.join(client.current_folder, 'buildinfo_b.json')) as f:
            buildinfo = json.load(f)
            print(buildinfo)

        @patch('conans.client.cache.cache.ClientCache.put_headers_path', new_callable=PropertyMock)
        @patch('conans.client.cache.cache.ClientCache.registry', new_callable=PropertyMock)
        @patch('conans.client.cache.cache.ClientCache.package_layout',
               new=client.cache.package_layout)
        @patch('conans.client.cache.cache.ClientCache.read_put_headers',
               new=client.cache.read_put_headers)
        def update(registry_mock, mock_put_headers_path):
            registry_mock.return_value = registry
            mock_put_headers_path.return_value = headers_path
            sys.argv = ['conan_build_info', 'update', 'buildinfo_a.json', 'buildinfo_b.json', '--output-file', 'mergedbuildinfo.json']
            run()

        with open(os.path.join(client.current_folder, 'mergedbuildinfo.json')) as f:
            buildinfo = json.load(f)
            print(buildinfo)
