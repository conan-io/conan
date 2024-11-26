import platform
import textwrap

from conan.test.utils.tools import TestClient


# TODO: Change this test when we refactor EnvVars. The UX leaves much to be desired
def test_env_and_scope_none():
    """
    Check scope=None does not append foo=var to conan{build|run}.{bat|sh|ps1}

    Issue: https://github.com/conan-io/conan/issues/17249
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.env import Environment
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"
            def generate(self):
                env1 = Environment()
                env1.define("foo", "var")
                # Will not append "my_env_file" to "conanbuild.bat|sh|ps1"
                envvars = env1.vars(self, scope=None)
                envvars.save_script("my_env_file")
                # Let's check the apply() function
                with env1.vars(self, scope=None).apply():
                    import os
                    assert os.environ["foo"] == "var"
            """)
    client.save({"conanfile.py": conanfile})
    client.run("install .")
    ext = ".bat" if platform.system() == "Windows" else ".sh"
    assert "my_env_file" not in client.load(f"conanbuild{ext}")
    assert "my_env_file" not in client.load(f"conanrun{ext}")

