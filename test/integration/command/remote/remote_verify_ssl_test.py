from conan.test.utils.tools import TestClient, TestRequester, TestServer


def requester(expected):
    class CheckVerifyRequester(TestRequester):

        def get(self, *args, **kwargs):
            verify = kwargs["verify"]
            assert verify == expected
            return super(CheckVerifyRequester, self).get(*args, **kwargs)
    return CheckVerifyRequester


class TestVerifySSL:

    def test_verify_ssl(self):
        server = TestServer()
        c = TestClient(servers={"default": server})
        c.run("remote remove default") # to remove from file, not from testing client

        c.run(f"remote add myremote {server.fake_url} --insecure")
        c.run("remote list")
        assert "Verify SSL: False" in c.out

        c.run(f"remote update myremote --secure")
        c.run("remote list")
        assert "Verify SSL: True" in c.out

        c.run("remote remove myremote")
        c.run(f"remote add myremote {server.fake_url}")
        c.run("remote list")
        assert "Verify SSL: True" in c.out

        # Verify that SSL is checked in requests
        c.requester_class = requester(True)
        c.run("search op* -r myremote")
        assert "WARN: There are no matching recipe references" in c.out

        # Verify that SSL is not checked in requests
        c.requester_class = requester(False)
        c.run(f"remote update myremote --insecure")
        c.run("search op* -r myremote")
        assert "WARN: There are no matching recipe references" in c.out

    def test_verify_certificate_per_remote(self):
        server1 = TestServer()
        server2 = TestServer()
        cert1 = "my/path/cert1"
        cert2 = "other/path/cert2"
        c = TestClient(servers={"server1": server1, "server2": server2})
        c.run("remote remove *") # to remove from file, not from testing client

        c.run(f"remote add server1 {server1.fake_url} --ca-path={cert1}")
        c.run(f"remote add server2 {server2.fake_url} --ca-path={cert2}")
        c.run("remote list")
        assert f"Verify SSL: {cert1}" in c.out
        assert f"Verify SSL: {cert2}" in c.out

        # Verify that SSL is checked in requests
        c.requester_class = requester(cert1)
        c.run("search op* -r server1")
        assert "WARN: There are no matching recipe references" in c.out

        c.requester_class = requester(cert2)
        c.run("search op* -r server2")
        assert "WARN: There are no matching recipe references" in c.out
        c.run(f"remote update server1 --ca-path={cert2}")
        c.run("search op* -r server2")
        assert "WARN: There are no matching recipe references" in c.out

    def test_verify_error_secure(self):
        c = TestClient()
        c.run(f"remote add server1 http://someurl --insecure=path1", assert_error=True)
        assert "argument --insecure: ignored explicit argument" in c.out
        c.run(f"remote add server1 http://someurl --ca-path", assert_error=True)
        assert "argument --ca-path: expected one argument" in c.out
        c.run(f"remote add server1 http://someurl --ca-path=path1 --ca-path=path2")
        # This WONT ERROR, but take the latest value (argparse limitations)
        c.run("remote list")
        assert f"Verify SSL: path2" in c.out

