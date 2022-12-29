import unittest

from conans.test.utils.tools import GenConanfile, TestClient


class InstallParallelTest(unittest.TestCase):

    def test_basic_parallel_install(self):
        client = TestClient(default_server_user=True)
        threads = 1  # At the moment, not really parallel until output implements mutex
        counter = 4
        client.run("config set general.parallel_download=%s" % threads)
        client.save({"conanfile.py": GenConanfile()})

        for i in range(counter):
            client.run("create . pkg%s/0.1@user/testing" % i)
        client.run("upload * --all --confirm")
        client.run("remove * -f")

        # Lets consume the packages
        conanfile_txt = ["[requires]"]
        for i in range(counter):
            conanfile_txt.append("pkg%s/0.1@user/testing" % i)
        conanfile_txt = "\n".join(conanfile_txt)

        client.save({"conanfile.txt": conanfile_txt}, clean_first=True)
        client.run("install .")
        self.assertIn("Downloading binary packages in %s parallel threads" % threads, client.out)
        for i in range(counter):
            self.assertIn("pkg%s/0.1@user/testing: Package installed" % i, client.out)
