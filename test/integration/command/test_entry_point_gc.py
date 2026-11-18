import gc
import os
import subprocess
import sys
import textwrap

import conan
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient


def test_entry_point_disables_gc():
    """ The real "conan" entry point, in a new process (TestClient doesn't use it), disables the
    cyclic garbage collector
    """
    code = textwrap.dedent("""
        import atexit, gc
        atexit.register(lambda: print("gc enabled:", gc.isenabled()))
        from conans.conan import run
        run()
        """)
    root = os.path.dirname(os.path.dirname(os.path.abspath(conan.__file__)))
    env = dict(os.environ, CONAN_HOME=temp_folder(), PYTHONPATH=root)
    result = subprocess.run([sys.executable, "-c", code, "--version"], cwd=temp_folder(), env=env,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "Conan version" in result.stdout
    assert "gc enabled: False" in result.stdout


def test_python_api_keeps_gc():
    """ The Python API, that TestClient uses in this process, doesn't disable the GC """
    assert gc.isenabled()
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    assert gc.isenabled()
