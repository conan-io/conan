import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save, load


custom_command = textwrap.dedent("""
    import os
    from conan.api.model import PkgReference, RecipeReference
    from conan.cli.command import conan_command


    @conan_command(group="custom commands")
    def metadata_download(conan_api, parser, *args):
        \"\"\"Download the metadata of one recipe/package revision to cwd (no cache).\"\"\"
        parser.add_argument("reference")
        parser.add_argument("-r", "--remote", required=True)
        a = parser.parse_args(*args)
        remote = conan_api.remotes.get(a.remote)
        if ":" in a.reference:
            pref = PkgReference.loads(a.reference)
            if pref.ref.revision is None:
                pref.ref = conan_api.list.latest_recipe_revision(pref.ref, remote)
            if pref.revision is None:
                pref = conan_api.list.latest_package_revision(pref, remote)
            conan_api.download.package_metadata(pref, remote, ["*"], os.getcwd())
        else:
            ref = RecipeReference.loads(a.reference)
            if ref.revision is None:
                ref = conan_api.list.latest_recipe_revision(ref, remote)
            conan_api.download.recipe_metadata(ref, remote, ["*"], os.getcwd())
    """)


def _server_with_metadata():
    c = TestClient(default_server_user=True, light=True)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    pid = c.created_package_id("pkg/0.1")
    c.run("cache path pkg/0.1 --folder=metadata")
    save(os.path.join(str(c.stdout).strip(), "logs", "recipe.log"), "recipe-log")
    c.run(f"cache path pkg/0.1:{pid} --folder=metadata")
    save(os.path.join(str(c.stdout).strip(), "logs", "build.log"), "build-log")
    c.run("upload * -c -r=default --metadata=*")
    c.run("remove * -c")
    c.save_home({"extensions/commands/cmd_metadata_download.py": custom_command})
    return c, pid


def test_metadata_download_recipe():
    c, _ = _server_with_metadata()
    c.run("metadata-download pkg/0.1 -r=default")
    assert load(os.path.join(c.current_folder, "metadata", "logs", "recipe.log")) == "recipe-log"
    c.run("list *")
    assert "There are no matching recipe references" in c.out


def test_metadata_download_package():
    c, pid = _server_with_metadata()
    c.run(f"metadata-download pkg/0.1:{pid} -r=default")
    assert load(os.path.join(c.current_folder, "metadata", "logs", "build.log")) == "build-log"
    c.run("list *")
    assert "There are no matching recipe references" in c.out
