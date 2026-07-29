import os
import textwrap

import pytest

from conan.internal.cache.home_paths import HomePaths
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.file_server import TestFileServer
from conan.test.utils.tools import TestClient


HEAVY_CONANFILE = textwrap.dedent("""
    import hashlib
    from conan import ConanFile
    from conan.errors import ConanException
    from conan.tools.files import download, save_backup_source, save

    class Heavy(ConanFile):
        name = "heavy"
        version = "0.1"
        requires = "dep/0.1"

        def generate(self):
            h = hashlib.sha256()
            for dep in self.dependencies.host.values():
                h.update(dep.ref.repr_notime().encode())
            key = h.hexdigest()
            url = f"gen-conan://{key}"
            out = "generated.txt"
            try:
                download(self, url, out, identifier=key, retry=0)
                self.output.info("GENCACHE hit")
            except ConanException:
                self.output.info("GENCACHE miss")
                save(self, out, "expensive output")
                save_backup_source(self, out, url, identifier=key)
""")


@pytest.fixture()
def producer():
    """Producer: creates dep + heavy, then uploads recipes to the Conan remote and
    the generated blob to the backup-sources mirror."""
    file_server = TestFileServer()
    backup_url = file_server.fake_url + "/genbackup/"

    c = TestClient(default_server_user=True, light=True)
    c.servers["file_server"] = file_server
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "heavy/conanfile.py": HEAVY_CONANFILE})
    c.save_home({"global.conf": f"core.sources:upload_url={backup_url}\n"})
    c.run("create dep")
    c.run("create heavy")
    assert "GENCACHE miss" in c.out

    c.run("upload * -r=default -c")     # recipes/binaries to the Conan remote
    c.run("cache backup-upload")        # generated blob to the backup mirror

    # Sanity: one blob (+ its .json) on the mirror, named by the identifier
    mirror_dir = os.path.join(file_server.store, "genbackup")
    blobs = [f for f in os.listdir(mirror_dir) if not f.endswith(".json")]
    assert len(blobs) == 1 and len(blobs[0]) == 64  # sha256 hex

    return c, file_server, backup_url


def _consumer(producer):
    """Fresh consumer sharing the producer's Conan remote and backup mirror."""
    producer_c, file_server, backup_url = producer
    conan_remotes = {k: v for k, v in producer_c.servers.items() if k != "file_server"}
    c = TestClient(servers=conan_remotes, inputs=["admin", "password"], light=True)
    c.servers["file_server"] = file_server
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "heavy/conanfile.py": HEAVY_CONANFILE})
    c.save_home({"global.conf": f"core.sources:download_urls=['{backup_url}']\n"})
    return c


def test_conan_create_reuses_uploaded_cache(producer):
    """Fresh `conan create` finds the generated blob on the mirror."""
    c2 = _consumer(producer)
    c2.run("create dep")
    c2.run("create heavy")
    assert "GENCACHE hit" in c2.out
    assert "GENCACHE miss" not in c2.out


def test_conan_install_local_reuses_uploaded_cache(producer):
    """Developer workflow: `conan install <path>` on the local heavy recipe."""
    c2 = _consumer(producer)
    c2.run("create dep")
    c2.run("install heavy")
    assert "GENCACHE hit" in c2.out
    assert "GENCACHE miss" not in c2.out


def test_no_download_urls_does_not_use_mirror(producer):
    """Without `core.sources:download_urls`, the consumer never contacts the mirror,
    even when the producer has uploaded there — so a fresh consumer misses. This
    isolates the role of `download_urls` as the wire-up between recipe and mirror."""
    producer_c, file_server, _ = producer
    conan_remotes = {k: v for k, v in producer_c.servers.items() if k != "file_server"}
    c = TestClient(servers=conan_remotes, inputs=["admin", "password"], light=True)
    c.servers["file_server"] = file_server
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "heavy/conanfile.py": HEAVY_CONANFILE})
    c.run("create dep")
    c.run("create heavy")
    assert "GENCACHE miss" in c.out
    assert "GENCACHE hit" not in c.out


def test_default_cache_folder_used_when_not_configured():
    """`identifier` works out of the box: with no `core.sources:*` configured, the
    default sources backup folder is used, so a second `create heavy` hits the
    local cache the first run seeded."""
    c = TestClient(light=True)
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "heavy/conanfile.py": HEAVY_CONANFILE})
    c.run("create dep")
    c.run("create heavy")
    assert "GENCACHE miss" in c.out

    # Second create: local (default) cache holds the entry saved by the first run.
    c.run("create heavy")
    assert "GENCACHE hit" in c.out
    assert "GENCACHE miss" not in c.out


def test_dep_rrev_change_produces_new_key():
    """Bumping dep's rrev changes the identifier → new miss + new cache entry."""
    c = TestClient(light=True)
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "heavy/conanfile.py": HEAVY_CONANFILE})
    c.run("create dep")
    c.run("create heavy")
    assert "GENCACHE miss" in c.out

    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1").with_import("import os")})
    c.run("create dep")
    c.run("create heavy")
    assert "GENCACHE miss" in c.out

    dl_cache = HomePaths(c.cache_folder).default_sources_backup_folder
    entries = os.listdir(os.path.join(dl_cache, "s"))
    blobs = [e for e in entries if not e.endswith(".json") and not e.endswith(".dirty")]
    assert len(blobs) == 2
