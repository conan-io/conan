import os
import textwrap

from conans.client.generators import relativize_generated_file
from conans.test.utils.mocks import ConanFileMock


def test_relativize(monkeypatch):
    conanfile = ConanFileMock()
    conanfile.folders.set_base_generators("/home/frodo")
    conanfile.folders.generators = "generators"
    content = textwrap.dedent("""\
        export PATH=/path/to/home/frodo:/home/frodo:/home/frodo/path/other
        export OTHER=/home/frodo/
        export PYTHON="/home/frodo/something":"/home/frodo/path with space/other"
        """)
    expected = textwrap.dedent("""\
        export PATH=/path/to/home/frodo:$$$/..:$$$/../path/other
        export OTHER=$$$/../
        export PYTHON="$$$/../something":"$$$/../path with space/other"
        """)
    monkeypatch.setattr(os.path, "exists", lambda _: True)
    result = relativize_generated_file(content, conanfile, "$$$")
    print(result)
    assert result == expected
