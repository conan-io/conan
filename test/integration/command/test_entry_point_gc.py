import gc
import os
import subprocess
import sys
import textwrap

import conan
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save


def _run_entry_point(args, cwd, home):
    """ The real "conan" entry point, in a new process (TestClient doesn't use it) """
    code = textwrap.dedent("""
        import atexit, gc
        atexit.register(lambda: print("gc enabled:", gc.isenabled(),
                                      "frozen:", gc.get_freeze_count() > 0))
        from conans.conan import run
        run()
        """)
    root = os.path.dirname(os.path.dirname(os.path.abspath(conan.__file__)))
    env = dict(os.environ, CONAN_HOME=home, PYTHONPATH=root)
    result = subprocess.run([sys.executable, "-c", code, *args], cwd=cwd, env=env,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result


def test_entry_point_disables_gc():
    """ The entry point disables the cyclic garbage collector """
    result = _run_entry_point(["--version"], cwd=temp_folder(), home=temp_folder())
    assert "Conan version" in result.stdout
    assert "gc enabled: False frozen: False" in result.stdout


def test_entry_point_enables_gc_for_builds():
    """ The installer enables it again while installing the packages, with the graph frozen """
    conanfile = textwrap.dedent("""
        import gc
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def requirements(self):
                self.output.info(f"gc in requirements(): {gc.isenabled()}")

            def build(self):
                self.output.info(f"gc in build(): {gc.isenabled()}")
        """)
    home = temp_folder()
    save(os.path.join(home, "profiles", "default"), "[settings]\nos=Linux")
    cwd = temp_folder()
    save(os.path.join(cwd, "conanfile.py"), conanfile)
    result = _run_entry_point(["create", "."], cwd=cwd, home=home)
    assert "pkg/0.1: gc in requirements(): False" in result.stderr
    assert "gc in build(): True" in result.stderr
    assert "gc enabled: False frozen: True" in result.stdout


def test_entry_point_frees_previous_graphs():
    """ A command can compute several graphs (test_package, workspace commands, custom commands
    running other commands): the ones no longer used are freed before computing a new one, also
    if they were frozen by the installer or had an error """
    command = textwrap.dedent('''
        import weakref
        from conan.cli.command import conan_command

        @conan_command(group="custom")
        def loop(conan_api, parser, *args):
            """ Runs some commands, are the nodes of their graphs still alive? """
            nodes = []
            for cmd in ("install .", "graph info --requires=missing/0.1", "install ."):
                result = conan_api.command.run(cmd, raise_on_errors=False)
                nodes.append(weakref.ref(result["graph"].root))
                del result
            print("alive:", [n() is not None for n in nodes])
        ''')
    home = temp_folder()
    save(os.path.join(home, "profiles", "default"), "[settings]\nos=Linux")
    save(os.path.join(home, "extensions", "commands", "cmd_loop.py"), command)
    cwd = temp_folder()
    save(os.path.join(cwd, "conanfile.txt"), "")
    result = _run_entry_point(["loop"], cwd=cwd, home=home)
    assert "alive: [False, False, True]" in result.stdout


def test_python_api_keeps_gc():
    """ The Python API, that TestClient uses in this process, doesn't disable the GC """
    assert gc.isenabled()
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    assert gc.isenabled()
    assert gc.get_freeze_count() == 0
