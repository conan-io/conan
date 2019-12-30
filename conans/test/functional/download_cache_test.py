import os
import textwrap
import unittest

from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.env_reader import get_env
from conans.util.files import load

#os.environ["TESTING_REVISIONS_ENABLED"] = "True"


#@unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "set TESTING_REVISIONS_ENABLED=1")
class DownloadCacheTest(unittest.TestCase):

    def test_download_skip(self):
        client = TestClient(default_server_user=True)
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
        cache_folder = temp_folder()
        log_trace_file = os.path.join(temp_folder(), "mylog.txt")
        client.run('config set storage.download_cache="%s"' % cache_folder)
        client.run('config set log.trace_file="%s"' % log_trace_file)
        client.run("remove * -f")
        client.run("install mypkg/0.1@user/testing")
        content = load(log_trace_file)
        print content
        return
        self.assertEqual(7, content.count('"_action": "DOWNLOAD"'))
        # 6 files cached, plus "locks" folder = 7
        self.assertEqual(7, len(os.listdir(cache_folder)))

        os.remove(log_trace_file)
        client.run("remove * -f")
        client.run('config set log.trace_file="%s"' % log_trace_file)
        client.run("install mypkg/0.1@user/testing")
        content = load(log_trace_file)
        print content
        self.assertEqual(0, content.count('"_action": "DOWNLOAD"'))
        self.assertIn("DOWNLOADED_RECIPE", content)
        self.assertIn("DOWNLOADED_PACKAGE", content)
