import os
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import save


def test_plugin_cmd_wrapper():
    c = TestClient()
    plugins = os.path.join(c.cache.cache_folder, "extensions", "plugins")
    wrapper = textwrap.dedent("""
        def cmd_wrapper(cmd):
            return 'echo "{}"'.format(cmd)
        """)
    # TODO: Decide name
    save(os.path.join(plugins, "cmd_wrapper.py"), wrapper)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def generate(self):
                self.run("Hello world")
                self.run("Other stuff")
        """)
    c.save({"conanfile.py": conanfile})
    c.run("install .")
    assert 'Hello world' in c.out
    assert 'Other stuff' in c.out
