import os
import sys
import textwrap
import unittest

from mock import patch, PropertyMock

from conans.model.graph_lock import LOCKFILE
from conans.build_info.command import run
from conans.test.utils.tools import TestClient


class MyBuildInfoCreation(unittest.TestCase):
    def test_build_info_start(self):
        client = TestClient()
        props_file = client.cache.put_headers_path
        sys.argv = ['conan_build_info', 'start', 'MyBuildName', '42']
        with patch('conans.client.cache.cache.ClientCache.put_headers_path',
                   new_callable=PropertyMock) as mock_put_headers_path:
            mock_put_headers_path.return_value = props_file
            run()
        with open(props_file) as f:
            content = f.read()
            self.assertIn('MyBuildName', content)
            self.assertIn('42', content)

    def test_build_info_stop(self):
        client = TestClient()
        props_file = client.cache.put_headers_path
        sys.argv = ['conan_build_info', 'stop']
        with patch('conans.client.cache.cache.ClientCache.put_headers_path',
                   new_callable=PropertyMock) as mock_put_headers_path:
            mock_put_headers_path.return_value = props_file
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
        with patch('conans.client.cache.cache.ClientCache.registry',
                   new_callable=PropertyMock) as registry_mock, patch(
            'conans.client.cache.cache.ClientCache.put_headers_path',
            new_callable=PropertyMock) as mock_put_headers_path, patch(
            'conans.client.cache.cache.ClientCache.package_layout',
            new=client.cache.package_layout), patch(
            'conans.client.cache.cache.ClientCache.read_put_headers',
            new=client.cache.read_put_headers):
            registry_mock.return_value = registry
            mock_put_headers_path.return_value = headers_path
            sys.argv = ['conan_build_info', 'start', 'MyBuildName', '42']
            run()
            sys.argv = ['conan_build_info', 'create', 'buildinfo.json', '--lockfile',
                        os.path.join(client.current_folder, LOCKFILE)]
            run()

    def test_build_info_update(self):
        pass
