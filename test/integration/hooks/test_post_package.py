import os
import textwrap

from conans.model.manifest import FileTreeManifest
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conans.util.files import save


def test_post_package():
    """ Test that 'post_package' hook is called before computing the manifest
    """
    t = TestClient()
    complete_hook = textwrap.dedent("""\
        import os
        from conan.tools.files import save
        def post_package(conanfile):
            save(conanfile, os.path.join(conanfile.package_folder, "myfile.txt"), "content!!")
        """)
    hook_path = os.path.join(t.cache.hooks_path, "complete_hook", "hook_complete.py")
    save(hook_path, complete_hook)
    t.save({'conanfile.py': GenConanfile("pkg", "0.1")})
    t.run("create .")
    pref_layout = t.created_layout()
    manifest = FileTreeManifest.load(pref_layout.package())
    assert "myfile.txt" in manifest.file_sums

    t.run("remove * -c")
    t.run("export-pkg .")
    pref_layout = t.created_layout()
    manifest = FileTreeManifest.load(pref_layout.package())
    assert "myfile.txt" in manifest.file_sums
