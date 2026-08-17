import os
import platform
import sys

import pytest


@pytest.mark.skipif(platform.system() != "Windows", reason="win_conpty.py needs pywinpty")
def test_captures_output_and_returncode():
    from conan.internal.conan_log.win_conpty import run_in_pseudo_console
    captured, returncode = run_in_pseudo_console([sys.executable, "-c",
                                                  "print('hello-conpty')"])
    assert returncode == 0
    assert "hello-conpty" in captured


@pytest.mark.skipif(platform.system() != "Windows", reason="win_conpty.py needs pywinpty")
def test_propagates_nonzero_exit_code():
    from conan.internal.conan_log.win_conpty import run_in_pseudo_console
    _, returncode = run_in_pseudo_console([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert returncode == 3


@pytest.mark.skipif(platform.system() != "Windows", reason="win_conpty.py needs pywinpty")
def test_child_sees_a_real_console():
    # The whole point of ConPTY: the child's own isatty() check must say True, same as the
    # POSIX pty test in test_command_log.py.
    from conan.internal.conan_log.win_conpty import run_in_pseudo_console
    code = "import sys; print('TTY' if sys.stdout.isatty() else 'NOTTY')"
    captured, returncode = run_in_pseudo_console([sys.executable, "-c", code])
    assert returncode == 0
    assert "TTY" in captured
    assert "NOTTY" not in captured


@pytest.mark.skipif(platform.system() != "Windows", reason="win_conpty.py needs pywinpty")
def test_respects_cwd():
    from conan.internal.conan_log.win_conpty import run_in_pseudo_console
    code = "import os; print(os.getcwd())"
    tmp_dir = os.environ.get("TEMP", "C:\\")
    captured, returncode = run_in_pseudo_console([sys.executable, "-c", code], cwd=tmp_dir)
    assert returncode == 0
    assert tmp_dir.rstrip("\\") in captured
