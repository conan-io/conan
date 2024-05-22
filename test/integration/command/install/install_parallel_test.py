import unittest

from conan.test.utils.tools import GenConanfile, TestClient


class InstallParallelTest(unittest.TestCase):

    def test_basic_parallel_install(self):
        client = TestClient(default_server_user=True)
        threads = 4
        counter = 8

        client.save_home({"global.conf": f"core.download:parallel={threads}"})
        client.save({"conanfile.py": GenConanfile()})

        for i in range(counter):
            client.run("create . --name=pkg%s --version=0.1 --user=user --channel=testing" % i)
        client.run("upload * --confirm -r default")
        client.run("remove * -c")

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
