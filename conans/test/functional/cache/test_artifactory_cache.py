import textwrap
from collections import OrderedDict

import requests

from conans.test.utils.tools import TestClient, TestRequester, TestServer





class TestArtifactoryCacheTestCase(object):

    def test_download(self):
        # Create a server with a known fake_url
        server_users = {"user": "password"}
        users = {"default": [("user", "password")]}
        server = TestServer(users=server_users, write_permissions=[("*/*@*/*", "*")])
        server.fake_url = 'http://fake-deterministic'

        # Declare a requester to gather the URL calls
        url_calls = []

        class Requester(TestRequester):
            def get(self_req, url, **kwargs):
                url_calls.append(url)
                return super(Requester, self_req).get(url, **kwargs)

        # Here it starts the actual test
        client = TestClient(servers={'default': server}, users=users)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                exports = "*"
                def package(self):
                    self.copy("*")
            """)
        client.save({"conanfile.py": conanfile,
                     "header.h": "header"})
        client.run("create . mypkg/0.1@user/testing")
        client.run("upload * --all --confirm")
        client.run("remove * -f")

        rt_sources_backup = 'https://rt.jfrog/backup_repo'
        client.run('config set storage.sources_backup="{}"'.format(rt_sources_backup))
        client.run('config set general.retry=0')
        client.requester_class = Requester
        client.run("install mypkg/0.1@user/testing")
        print(client.out)
        print('\n'.join(url_calls))

        assert False
