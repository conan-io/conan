import os
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import save


def test_pkg_sign():
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_exports("export/*")
            .with_exports_sources("export_sources/*").with_package_file("myfile", "mycontents!"),
            "export/file1.txt": "file1!",
            "export_sources/file2.txt": "file2!"})
    signer = textwrap.dedent(r"""
        import os

        def sign(ref, files, folder):
            print("Signing ref: ", ref)
            print("Signing files: ", files)
            signature = os.path.join(folder, "signature.asc")
            open(signature, "w").write("\n".join(files))
            return ["signature.asc"]

        def verify(ref, files, folder):
            print("Verifying ref: ", ref)
            print("Verifying files: ", files)
            signature = os.path.join(folder, "signature.asc")
            contents = open(signature).read()
            print("verifying contents", contents)
            for f in files:
                assert f in contents
        """)
    save(os.path.join(c.cache.plugins_path, "sign", "sign.py"), signer)
    c.run("create .")
    c.run("upload * -r=default -c")
    assert "Signing ref:  pkg/0.1" in c.out
    assert "Signing ref:  pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709" in c.out
    c.run("remove * -f")
    c.run("install --requires=pkg/0.1")
    print(c.out)
    assert "Verifying ref:  pkg/0.1" in c.out
    assert "Verifying ref:  pkg/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709" in c.out
