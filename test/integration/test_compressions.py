from conan.test.utils.tools import TestClient


def test_xz():
    c = TestClient(default_server_user=True)
    c.save_home({"global.conf": "core.upload:compression_format=xz"})
    c.run("new header_lib")
    c.run("create -tf=")
    c.run("upload * -r=default -c")
    print(c.out)
    c.run("remove * -c")
    c.run("install --requires=mypkg/0.1")
    print(c.out)
    c.run("cache path mypkg/0.1")
    print(c.out)
    c.run("cache path mypkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709")
    print(c.out)
