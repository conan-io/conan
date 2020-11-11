import textwrap
import unittest

from parameterized.parameterized import parameterized_class

from conans.client.remote_manager import CONAN_REQUEST_HEADER_SETTINGS
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer, TestRequester


class RequesterClass(TestRequester):
    requests = None

    def __init__(self, *args, **kwargs):
        self.requests = []
        super(RequesterClass, self).__init__(*args, **kwargs)

    def get(self, url, headers=None, **kwargs):
        self.requests.append((url, headers))
        return super(RequesterClass, self).get(url, headers=headers, **kwargs)


@parameterized_class([{"revs_enabled": True}, {"revs_enabled": False}, ])
class RequestSettingsHeaderTestCase(unittest.TestCase):
    """ Conan adds a header with the settings used to compute the package ID """

    profile = textwrap.dedent("""
        [settings]
        os=Macos
        arch=x86_64
        compiler=apple-clang
        compiler.version=11.0
        compiler.libcxx=libc++
    """)

    def setUp(self):
        test_server = TestServer(users={"user": "mypass"})
        self.servers = {"default": test_server}
        t = TestClient(servers=self.servers, users={"default": [("user", "mypass")]})
        t.save({'conanfile.py': GenConanfile().with_settings('os', 'arch', 'compiler'),
                'profile': self.profile})
        t.run('create conanfile.py name/version@user/channel --profile:host=profile')
        t.run('upload name/version@user/channel --all')

    def _get_settings_headers(self, requester):
        hits = sum([CONAN_REQUEST_HEADER_SETTINGS in headers for _, headers in requester.requests])
        self.assertEquals(hits, 2 if self.revs_enabled else 1)
        for url, headers in requester.requests:
            if CONAN_REQUEST_HEADER_SETTINGS in headers:
                if self.revs_enabled:
                    self.assertTrue(url.endswith('/latest'), msg=url)
                else:
                    self.assertTrue(url.endswith('/download_urls'), msg=url)
                return headers.get(CONAN_REQUEST_HEADER_SETTINGS)

    def _assert_settings_headers(self, settings_header, compiler_version='11.0'):
        # It takes only the values that are relevant to the recipe
        self.assertListEqual(
            sorted(['os', 'arch', 'compiler', 'compiler.version', 'compiler.libcxx']),
            sorted([it.split('=', 1)[0] for it in settings_header.split(';')]))
        self.assertIn('os=Macos', settings_header)
        self.assertIn('arch=x86_64', settings_header)
        self.assertIn('compiler=apple-clang', settings_header)
        self.assertIn('compiler.libcxx=libc++', settings_header)
        self.assertIn('compiler.version={}'.format(compiler_version), settings_header)
        self.assertNotIn('build_type', settings_header)

    def _get_test_client(self):
        t = TestClient(requester_class=RequesterClass, servers=self.servers,
                       users={"default": [("user", "mypass")]})
        t.run('config set general.revisions_enabled={}'.format('1' if self.revs_enabled else '0'))
        return t

    def test_install_recipe_mismatch(self):
        t = self._get_test_client()
        t.save({'profile': self.profile})
        t.run('install failing/version@user/channel --profile=profile', assert_error=True)
        self.assertFalse(any([CONAN_REQUEST_HEADER_SETTINGS in headers for _, headers in
                              t.api.http_requester.requests]))

    def test_install_package_match(self):
        t = self._get_test_client()
        t.save({'profile': self.profile})

        # Package match
        t.run('install name/version@user/channel --profile=profile -s build_type=Release')
        settings_header = self._get_settings_headers(t.api.http_requester)
        self._assert_settings_headers(settings_header)

        # Package mismatch
        t.run('install name/version@user/channel --profile=profile -s compiler.version=12.0',
              assert_error=True)
        settings_header = self._get_settings_headers(t.api.http_requester)
        self._assert_settings_headers(settings_header, compiler_version='12.0')

    def test_info_package_match(self):
        t = self._get_test_client()
        t.save({'profile': self.profile})

        # Package match
        t.run('info name/version@user/channel --profile=profile -s build_type=Release')
        settings_header = self._get_settings_headers(t.api.http_requester)
        self._assert_settings_headers(settings_header)

        # Package mismatch
        t.run('info name/version@user/channel --profile=profile -s compiler.version=12.0')
        settings_header = self._get_settings_headers(t.api.http_requester)
        self._assert_settings_headers(settings_header, compiler_version='12.0')

    def test_install_as_requirement(self):
        t = self._get_test_client()
        t.save({'conanfile.py': GenConanfile().with_requires('name/version@user/channel'),
                'profile': self.profile})

        # Requirement is found
        t.run('install . consumer/version@ --profile=profile -s compiler.version=11.0')
        settings_header = self._get_settings_headers(t.api.http_requester)
        self._assert_settings_headers(settings_header)

        # Requirement is not found
        t.run('install . consumer/version@ --profile=profile -s compiler.version=12.0',
              assert_error=True)
        settings_header = self._get_settings_headers(t.api.http_requester)
        self._assert_settings_headers(settings_header, compiler_version='12.0')
