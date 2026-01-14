"""
Tests for authentication concurrency issues during parallel downloads.

This test verifies that when multiple threads download packages in parallel
and the JWT token expires, only one thread requests new credentials while
others wait and reuse the new token.
"""

import os
import tempfile
import time

from conan.test.utils.tools import TestClient, TestServer
from conan.test.assets.genconanfile import GenConanfile
from conan.internal.api.remotes.localdb import LocalDB
from conan.internal.util.files import save


def test_concurrent_download_token_expiry():
    """
    Test that concurrent downloads handle token expiry correctly.

    When multiple threads download packages in parallel and the JWT token
    expires, authentication should be serialized so only one thread requests
    credentials while others wait and reuse the updated token.

    This prevents the "inputs exhausted" error that occurred when multiple
    threads tried to get credentials simultaneously.
    """
    # Create server with very short token expiration
    server_folder = tempfile.mkdtemp()
    server_conf = """
[server]
disk_authorize_timeout: 0
disk_storage_path: ./data
updown_secret: 12345
jwt_secret: mysecret
jwt_expire_minutes: 0.1
port: 12345
[read_permissions]
*/*@*/*: *
[write_permissions]
*/*@*/*: admin
"""
    save(os.path.join(server_folder, ".conan_server", "server.conf"), server_conf)
    server = TestServer(base_path=server_folder, users={"admin": "password", "user": "pass"})

    # Create client with multiple packages to force parallel downloads
    # Only provide credentials twice: once for upload, once for download after expiry
    c = TestClient(servers={"default": server}, inputs=["admin", "password", "user", "pass"])

    # Create multiple packages to trigger parallel downloads
    for i in range(5):
        conanfile = GenConanfile(f"pkg{i}", "1.0").with_settings("os")
        c.save({"conanfile.py": conanfile})
        c.run(f"create . -s os=Linux")

    # Upload all packages
    c.run("upload * -r=default -c")

    # Verify initial authentication
    localdb = LocalDB(c.cache_folder)
    user, token, _ = localdb.get_login(server.fake_url)
    assert user == "admin"
    assert token is not None

    # Wait for token to expire
    time.sleep(7)

    # Remove local cache to force download
    c.run("remove * -c")

    # Clear users to force re-authentication
    c.users = {}

    # Install all packages, which will:
    # 1. Download recipes (will use "user", "pass")
    # 2. Download packages in parallel (48 threads)
    # 3. With only one set of credentials in inputs, this would fail
    #    if multiple threads tried to authenticate simultaneously
    # 4. With the fix, only one thread authenticates, others wait and reuse token
    c.run("install --requires=pkg0/1.0 --requires=pkg1/1.0 --requires=pkg2/1.0 "
          "--requires=pkg3/1.0 --requires=pkg4/1.0 -s os=Linux")

    # Verify authentication succeeded
    assert "Remote 'default' needs authentication, obtaining credentials" in c.out

    # Verify we authenticated with the second user
    user, token, _ = localdb.get_login(server.fake_url)
    assert user == "user"
    assert token is not None

    # Most importantly: we didn't exhaust inputs
    # If multiple threads tried to authenticate simultaneously,
    # we would have gotten "Class MockedInputStream: There are no more inputs"
    assert "There are no more inputs" not in c.out

    # Verify all packages were downloaded successfully
    for i in range(5):
        assert f"pkg{i}/1.0" in c.out
