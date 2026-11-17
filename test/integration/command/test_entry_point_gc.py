import os
import subprocess
import sys
import textwrap

import conan
from conan.test.utils.test_files import temp_folder


def test_entry_point_disables_gc():
    """ The real "conan" entry point, in a new process (TestClient doesn't use it), disables the
    cyclic garbage collector. The Python API doesn't
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
