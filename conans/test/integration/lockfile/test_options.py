import json
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.xfail(reason="lockfiles wip")
def test_options():
    client = TestClient()
    ffmpeg = textwrap.dedent("""
        from conans import ConanFile
        class FfmpegConan(ConanFile):
            options = {"variation": ["standard", "nano"]}
            default_options = {"variation": "standard"}

            def build(self):
                self.output.info("Variation %s!!" % self.options.variation)
        """)

    variant = textwrap.dedent("""
        from conans import ConanFile
        class Meta(ConanFile):
            requires = "ffmpeg/1.0"
            default_options = {"ffmpeg:variation": "nano"}
        """)

    client.save({"ffmepg/conanfile.py": ffmpeg,
                 "variant/conanfile.py": variant})
    client.run("export ffmepg ffmpeg/1.0@")
    client.run("export variant nano/1.0@")

    client.run("lock create --reference=nano/1.0@ --build --lockfile-out=conan.lock")
    lockfile = client.load("conan.lock")
    # assert '"options": "variation=nano"' in lockfile

    client.run("lock build-order conan.lock --lockfile-out=conan.lock --build=missing "
               "--json=build_order.json")

    json_file = client.load("build_order.json")
    to_build = json.loads(json_file)
    f = to_build[0]

    cmd = "install --reference={} --build={} {} --lockfile=conan.lock".format(f[0], f[0], f[3])
    client.run(cmd)
    assert "ffmpeg/1.0: Variation nano!!" in client.out
