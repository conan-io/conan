import unittest

from conans import API_V2
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient, TestServer


class DownloadRetriesTest(unittest.TestCase):

    def test_do_not_retry_when_missing_file(self):

        test_server = TestServer(server_capabilities=[API_V2])
        client = TestClient(servers={"default": test_server},
                            users={"default": [("lasote", "mypass")]})
        conanfile = '''from conans import ConanFile
class MyConanfile(ConanFile):
    pass
'''
        client.save({CONANFILE: conanfile})
        client.run("create . Pkg/0.1@lasote/stable")
        client.run("upload '*' -c --all")
        self.assertEquals(str(client.out).count("seconds to retry..."), 0)

    def test_recipe_download_retry(self):
        test_server = TestServer()
        client = TestClient(servers={"default": test_server},
                            users={"default": [("lasote", "mypass")]})

        conanfile = '''from conans import ConanFile
class MyConanfile(ConanFile):
    pass
'''
        client.save({CONANFILE: conanfile})
        client.run("create . Pkg/0.1@lasote/stable")
        client.run("upload '*' -c --all")

        class Response(object):
            ok = None
            status_code = None
            charset = None
            headers = {}

            def __init__(self, ok, status_code):
                self.ok = ok
                self.status_code = status_code

            @property
            def content(self):
                if not self.ok:
                    raise Exception("Bad boy")
                else:
                    return b'{"conanfile.py": "path/to/fake/file"}'

            text = content

        class BuggyRequester(object):

            def __init__(self, *args, **kwargs):
                pass

            def get(self, *args, **kwargs):
                if "path/to/fake/file" not in args[0]:
                    return Response(True, 200)
                else:
                    return Response(False, 200)

        # The buggy requester will cause a failure only downloading files, not in regular requests
        client = TestClient(servers={"default": test_server},
                            users={"default": [("lasote", "mypass")]},
                            requester_class=BuggyRequester)
        error = client.run("install Pkg/0.1@lasote/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertEquals(str(client.out).count("Waiting 0 seconds to retry..."), 2)
        self.assertEquals(str(client.out).count("ERROR: Error 200 downloading"), 3)
