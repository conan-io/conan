import time

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer


def test_no_update():
    servers = {"server1": TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                     users={"lasote": "mypass"}),
               "server2": TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                     users={"lasote": "mypass"}),
               "server3": TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                     users={"lasote": "mypass"})}
    client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
    client2 = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
    # create the same revision several times and upload to all the servers
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0")})
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0")})

    # upload the same revision, will have different timestamps on each server
    client.run("create .")
    client.run("upload liba/1.0.0 -r server1")
    time.sleep(0.1)
    client.run("upload liba/1.0.0 -r server2")
    time.sleep(0.1)
    client.run("upload liba/1.0.0 -r server3")

    # to create a new rrev
    client.save({"conanfile.py": GenConanfile("liba", "1.0.0").with_provides("somelib/1.0.0")})

    client.run("install liba/1.0.0@")

    # empty the cache
    client.run("remove * -f -c")

    # will not find revisions for the recipe -> search all remotes and install the
    # latest revision between all of them
    client.run("install liba/1.0.0@")
