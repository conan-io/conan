import re
import unittest

from conans.test.utils.tools import GenConanfile, TestClient


class DownloadParallelTest(unittest.TestCase):

    def test_basic_parallel_download(self):
        client = TestClient(default_server_user=True)
        threads = 1  # At the moment, not really parallel until output implements mutex
        counter = 4
        client.run("config set general.parallel_download=%s" % threads)
        client.save({"conanfile.py": GenConanfile().with_option("myoption", '"ANY"')})

        package_ids = []
        for i in range(counter):
            client.run("create . pkg/0.1@user/testing -o pkg:myoption=%s" % i)
            package_id = re.search(r"pkg/0.1@user/testing:(\S+)", str(client.out)).group(1)
            package_ids.append(package_id)
        client.run("upload * --all --confirm")
        client.run("remove * -f")

        # Lets download the packages
        client.run("download pkg/0.1@user/testing")
        self.assertIn("Downloading binary packages in %s parallel threads" % threads, client.out)
        for package_id in package_ids:
            assert f"pkg/0.1@user/testing: Package installed {package_id}" in client.out
