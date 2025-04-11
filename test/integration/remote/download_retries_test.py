from conan.internal.paths import CONANFILE
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, TestServer, TestRequester


class TestDownloadRetries:

    def test_recipe_download_retry(self):
        test_server = TestServer()
        client = TestClient(servers={"default": test_server}, inputs=["admin", "password"])

        client.save({CONANFILE: GenConanfile()})
        client.run("create . --name=pkg --version=0.1 --user=lasote --channel=stable")
        client.run("upload '*' -c -r default")

        class Response:
            def __init__(self, ok, status_code):
                self.ok = ok
                self.status_code = status_code

        class BuggyRequester(TestRequester):
            def get(self, *args, **kwargs):
                if "files/conanfile.py" not in args[0]:
                    return super(BuggyRequester, self).get(*args, **kwargs)
                else:
                    return Response(False, 200)

        # The buggy requester will cause a failure only downloading files, not in regular requests
        client = TestClient(servers={"default": test_server}, inputs=["admin", "password"],
                            requester_class=BuggyRequester)
        client.run("install --requires=pkg/0.1@lasote/stable", assert_error=True)
        assert str(client.out).count("Waiting 0 seconds to retry...") == 2
        assert str(client.out).count("Error 200 downloading") == 3
