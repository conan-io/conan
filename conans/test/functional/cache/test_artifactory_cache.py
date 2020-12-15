import textwrap
from collections import OrderedDict

import requests

from client.downloaders.utils import hash_url
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
        client = TestClient(servers={'default': server}, users=users, requester_class=Requester)
        rt_sources_backup = 'https://rt.jfrog/backup_repo'
        client.run('config set storage.sources_backup="{}"'.format(rt_sources_backup))
        client.run('config set general.retry=0')
        conanfile = textwrap.dedent("""
            from conans import ConanFile, tools

            class Pkg(ConanFile):
                exports = "*"

                def source(self):
                    try:
                        tools.get('http://no.checksum.file')
                    except Exception:
                        pass
                    try:
                        tools.get('http://yes.checksum.file', md5='md5_chechsum')
                    except Exception:
                        pass

                def package(self):
                    self.copy("*")
            """)
        client.save({"conanfile.py": conanfile, "header.h": "header"})

        # Create command will download files in the 'source' method
        client.run("create . mypkg/0.1@user/testing")
        assert len(url_calls) == 3
        assert url_calls[0] == 'http://no.checksum.file'
        yes_checksum_hash = hash_url('http://yes.checksum.file', 'md5_chechsum', False)
        assert url_calls[1] == '{}/{}'.format(rt_sources_backup, yes_checksum_hash)
        assert url_calls[2] == 'http://yes.checksum.file'
        url_calls.clear()

        client.run("upload * --all --confirm")
        client.run("remove * -f")

        # Install command doesn't use Artifactory cache
        client.run("install mypkg/0.1@user/testing")
        assert not any(it.startswith(rt_sources_backup) for it in url_calls)
