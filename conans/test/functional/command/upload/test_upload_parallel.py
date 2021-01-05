import textwrap

from mock import patch
from requests import ConnectionError

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID, TestRequester


def test_upload_parallel_error():
    """Cause an error in the parallel transfer and see some message"""

    class FailOnReferencesUploader(TestRequester):
        fail_on = ["lib1", "lib3"]

        def put(self, *args, **kwargs):
            if any(ref in args[0] for ref in self.fail_on):
                raise ConnectionError("Connection fails with lib2 and lib4 references!")
            else:
                return super(FailOnReferencesUploader, self).put(*args, **kwargs)

    client = TestClient(requester_class=FailOnReferencesUploader, default_server_user=True)
    client.save({"conanfile.py": GenConanfile()})
    client.run('user -p password -r default user')
    for index in range(4):
        client.run('create . lib{}/1.0@user/channel'.format(index))
    client.run('upload lib* --parallel -c --all -r default --retry-wait=0', assert_error=True)
    assert "Connection fails with lib2 and lib4 references!" in client.out
    assert "Execute upload again to retry upload the failed files" in client.out


def test_upload_parallel_success():
    """Upload 2 packages in parallel with success"""

    client = TestClient(default_server_user=True)
    client.save({"conanfile.py": GenConanfile()})
    client.run('create . lib0/1.0@user/channel')
    assert "lib0/1.0@user/channel: Package '{}' created".format(NO_SETTINGS_PACKAGE_ID) in client.out
    client.run('create . lib1/1.0@user/channel')
    assert "lib1/1.0@user/channel: Package '{}' created".format(NO_SETTINGS_PACKAGE_ID) in client.out
    client.run('user -p password -r default user')
    client.run('upload lib* --parallel -c --all -r default')
    assert "Uploading lib0/1.0@user/channel to remote 'default'" in client.out
    assert "Uploading lib1/1.0@user/channel to remote 'default'" in client.out
    client.run('search lib0/1.0@user/channel -r default')
    assert "lib0/1.0@user/channel" in client.out
    client.run('search lib1/1.0@user/channel -r default')
    assert "lib1/1.0@user/channel" in client.out


def test_upload_parallel_fail_on_interaction():
    """Upload 2 packages in parallel and fail because non_interactive forced"""

    client = TestClient(default_server_user=True)
    client.save({"conanfile.py": GenConanfile()})
    num_references = 2
    for index in range(num_references):
        client.run('create . lib{}/1.0@user/channel'.format(index))
        assert "lib{}/1.0@user/channel: Package '{}' created".format(
            index,
            NO_SETTINGS_PACKAGE_ID) in client.out
    client.run('user -c')
    client.run('upload lib* --parallel -c --all -r default', assert_error=True)
    assert "ERROR: lib0/1.0@user/channel: Upload recipe to 'default' failed: " \
           "Conan interactive mode disabled. [Remote: default]" in client.out


def test_beat_character_long_upload():
    client = TestClient(default_server_user=True)
    slow_conanfile = textwrap.dedent("""
        from conans import ConanFile
        class MyPkg(ConanFile):
            exports = "*"
            def package(self):
                self.copy("*")
        """)
    client.save({"conanfile.py": slow_conanfile,
                 "hello.cpp": ""})
    client.run("create . pkg/0.1@user/stable")
    client.run("user user --password=password")
    with patch("conans.util.progress_bar.TIMEOUT_BEAT_SECONDS", -1):
        with patch("conans.util.progress_bar.TIMEOUT_BEAT_CHARACTER", "%&$"):
            client.run("upload pkg/0.1@user/stable --all")
    out = "".join(str(client.out).splitlines())
    assert "Compressing package...%&$%&$Uploading conan_package.tgz -> pkg/0.1@user/stable:5ab8" \
           in out
    assert "%&$Uploading conan_export.tgz" in out
    assert "%&$Uploading conaninfo.txt" in out
