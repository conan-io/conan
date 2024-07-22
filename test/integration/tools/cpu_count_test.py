import textwrap

from conan.test.utils.tools import TestClient


class TestNJobs:

    def test_cpu_count_override(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.build import build_jobs

            class Conan(ConanFile):
                name = "hello0"
                version = "0.1"

                def build(self):
                    self.output.warning("CPU COUNT=> %s" % build_jobs(self))
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . -c tools.build:jobs=5")
        assert "CPU COUNT=> 5" in client.out
