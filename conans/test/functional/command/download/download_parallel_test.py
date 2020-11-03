import unittest

from conans.test.utils.tools import GenConanfile, TestClient


class DownloadParallelTest(unittest.TestCase):

    def test_basic_parallel_download(self):
        client = TestClient(default_server_user=True)
        threads = 1  # At the moment, not really parallel until output implements mutex
        counter = 4
        client.run("config set general.parallel_download=%s" % threads)
        client.save({"conanfile.py": GenConanfile().with_option("myoption", '"ANY"')})

        for i in range(counter):
            client.run("create . pkg/0.1@user/testing -o pkg:myoption=%s" % i)
        client.run("upload * --all --confirm")
        client.run("remove * -f")

        # Lets download the packages
        client.run("download pkg/0.1@user/testing")
        self.assertIn("Downloading binary packages in %s parallel threads" % threads, client.out)
        self.assertIn("pkg/0.1@user/testing: Package installed "
                      "74ca4e392408c388db596b086fca5ebf64d825c0", client.out)
        self.assertIn("pkg/0.1@user/testing: Package installed "
                      "522dbc702b9cc2b582607ad6525f32ebd1442be5", client.out)
        self.assertIn("pkg/0.1@user/testing: Package installed "
                      "11997e24a862625b5e4753858f71aaf81a58a9b4", client.out)
        self.assertIn("pkg/0.1@user/testing: Package installed "
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", client.out)
