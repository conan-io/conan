import textwrap

import mock
from requests import Response

from conans.test.utils.tools import TestClient, TestRequester


def test_remote_generic_user_operations():
    client = TestClient()
    client.run("remote add foo http://foo.com --generic")
    client.run("remote login foo my_user -p my_pass")
    assert "Changed user of remote 'foo' from 'None' (anonymous) to " \
           "'my_user' (authenticated)" in client.out
    client.run("remote list")
    assert "foo: http://foo.com [Verify SSL: True, Enabled: True, Type: generic]" in client.out
    client.run("remote list-users")
    assert "foo:\n  Username: my_user\n  authenticated: True\n" in client.out
    client.run("remote logout foo")
    assert "Changed user of remote 'foo' from 'my_user' (authenticated) to " \
           "'None' (anonymous)" in client.out
    client.run("remote list-users")
    assert "foo:\n  No user\n" in client.out


def test_remote_generic_download():
    class MyHttpRequester(TestRequester):

        def get(self, url, **kwargs):
            assert url == 'http://foo.com/relative/path/file.txt'
            assert kwargs["auth"] == ("my_user", "my_pass")
            ret = Response()
            ret.status_code = 200
            ret._content = b''
            return ret

    client = TestClient(requester_class=MyHttpRequester)
    client.run("remote add foo http://foo.com --generic")
    client.run("remote login foo my_user -p my_pass")
    conanfile = textwrap.dedent("""
                from conans import ConanFile
                from conan.tools.files import download

                class Pkg(ConanFile):
                    def source(self):
                        download(self, "/relative/path/file.txt", "file.txt", remote="foo")
                """)

    client.save({"conanfile.py": conanfile})
    client.run("create . boo/1.0@")
