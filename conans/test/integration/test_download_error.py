from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_download_error():
    c = TestClient(default_server_user=True)
    c.save({"gtest/conanfile.py": GenConanfile("gtest", "0.1"),
            "dep/conanfile.py": GenConanfile("dep", "0.1").with_test_requires("gtest/0.1"),
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requirement("dep/0.1")
                                                          .with_test_requires("gtest/0.1")})
    c.run("create gtest")
    c.run("export dep")
    c.run("export pkg")
    c.run("upload * -r=default -c")
    c.run("remove * -f")
    c.run("install --requires=pkg/0.1 --build=missing")
    print(c.out)
