import pytest

from conan.test.utils.tools import GenConanfile, TestClient


class TestInstallParallel:

    @pytest.mark.parametrize("counter", [2, 8])
    def test_basic_parallel_install(self, counter):
        client = TestClient(default_server_user=True)
        threads = 4

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
        assert "Downloading binary packages in %s parallel threads" % min(threads, counter) in client.out
        for i in range(counter):
            assert "pkg%s/0.1@user/testing: Package installed" % i in client.out
