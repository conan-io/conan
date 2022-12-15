import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_regular_package():
    client = TestClient()
    # TODO: This is hardcoded
    profile = textwrap.dedent("""
        [tool_requires]
        tool*:pkga/1.0.0@
        """)
    client.run("config set general.revisions_enabled=1")
    client.save({"pkga/conanfile.py": GenConanfile(),
                 "tool/conanfile.py": GenConanfile().with_requires("pkga/[>=1.0.0]"),
                 "app/conanfile.py": GenConanfile().with_require("pkga/1.0.0").with_build_requires(
                     "tool/1.0.0"),
                 "myprofile": profile})  # version range in app

    # export different version from the libs to the cache
    client.run("export pkga pkga/1.0.0@")
    client.run("export pkga pkga/1.1.0@")  # This starts the misery
    client.run("export tool tool/1.0.0@")
    client.run("export app  app/1.0.0@")

    client.run(
        "lock create --reference app/1.0.0@  --lockfile-out app.lock --build outdated --profile=myprofile --profile:build=myprofile")
    print(client.load("app.lock"))
