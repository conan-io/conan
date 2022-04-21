import platform
import re

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Autotools")
def test_link_lib_correct_order():
    client = TestClient()
    liba = GenConanfile().with_name("liba").with_version("0.1")
    libb = GenConanfile().with_name("libb").with_version("0.1").with_require("liba/0.1")
    libc = GenConanfile().with_name("libc").with_version("0.1").with_require("libb/0.1")
    consumer = GenConanfile().with_require("libc/0.1")
    client.save({"liba.py": liba, "libb.py": libb, "libc.py": libc, "consumer.py": consumer})
    client.run("create liba.py")
    client.run("create libb.py")
    client.run("create libc.py")
    client.run("install consumer.py -g AutotoolsDeps")
    deps = client.load("conanautotoolsdeps.sh")
    # check the libs are added in the correct order with this regex
    assert re.search("export LDFLAGS.*libc.*libb.*liba", deps)
