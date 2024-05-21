import json
import textwrap

from conan.test.utils.tools import TestClient


def test_options():
    """ lockfiles no longer contains option or any other configuration information. Instead
    the ``graph build-order`` applying a lockfile will return the necessary options to build
    it in order
    """
    client = TestClient()
    ffmpeg = textwrap.dedent("""
        from conan import ConanFile
        class FfmpegConan(ConanFile):
            options = {"variation": ["standard", "nano"]}
            default_options = {"variation": "standard"}

            def build(self):
                self.output.info("Variation %s!!" % self.options.variation)
        """)

    variant = textwrap.dedent("""
        from conan import ConanFile
        class Meta(ConanFile):
            requires = "ffmpeg/1.0"
            default_options = {"ffmpeg/1.0:variation": "nano"}
        """)

    client.save({"ffmepg/conanfile.py": ffmpeg,
                 "variant/conanfile.py": variant})
    client.run("export ffmepg --name=ffmpeg --version=1.0")
    client.run("export variant --name=nano --version=1.0")
    client.run("lock create --requires=nano/1.0@ --build=*")
    client.run("graph build-order --requires=nano/1.0@ "
               "--lockfile-out=conan.lock --build=missing "
               "--format=json", redirect_stdout="build_order.json")

    json_file = client.load("build_order.json")
    to_build = json.loads(json_file)
    ffmpeg = to_build[0][0]
    ref = ffmpeg["ref"]
    options = " ".join(f"-o {option}" for option in ffmpeg["packages"][0][0]["options"])

    cmd = "install --requires={} --build={} {}".format(ref, ref, options)
    client.run(cmd)
    assert "ffmpeg/1.0: Variation nano!!" in client.out
