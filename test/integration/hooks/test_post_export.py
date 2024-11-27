import os
import textwrap

from conans.model.manifest import FileTreeManifest
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conans.util.files import save


def test_called_before_digest():
    """ Test that 'post_export' hook is called before computing the digest of the
        exported folders
    """
    t = TestClient()
    complete_hook = textwrap.dedent("""\
        import os
        from conan.tools.files import save
        def post_export(conanfile):
            save(conanfile, os.path.join(conanfile.export_folder, "myfile.txt"), "content!!")
        """)
    hook_path = os.path.join(t.cache.hooks_path, "complete_hook", "hook_complete.py")
    save(hook_path, complete_hook)
    t.save({'conanfile.py': GenConanfile("pkg", "0.1")})
    t.run("export .")
    ref_layout = t.exported_layout()
    manifest = FileTreeManifest.load(ref_layout.export())
    assert "myfile.txt" in manifest.file_sums
