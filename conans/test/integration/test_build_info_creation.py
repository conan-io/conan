import sys
import textwrap
import unittest

from mock import patch, PropertyMock

from conans.build_info.command import run
from conans.test.utils.tools import TestClient, TestServer


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
                """)
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile.format(requires="")})
        client.run("create . PkgA/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(requires='requires = "PkgA/0.1@user/channel"')})
        client.run("create . PkgB/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(requires='requires = "PkgB/0.1@user/channel"')})
        client.run("create . PkgC/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(requires='requires = "PkgC/0.1@user/channel"')})
        client.run("create . PkgD/0.1@user/channel")


        pass

    def test_build_info_update(self):
        pass
