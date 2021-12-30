import os
import re
import textwrap

from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import save


class TestCacheCompatibles:

    def test_compatible_build_type(self):
        client = TestClient()
        compatibles = textwrap.dedent("""\
            def compatibility(conanfile):
                result = []
                if conanfile.settings.build_type == "Debug":
                    result.append(["settings", "build_type", "Release"])
                return result
            """)
        save(os.path.join(client.cache.plugins_path, "binary_compatibility.py"), compatibles)
        client.save({"dep/conanfile.py": GenConanfile().with_setting("build_type"),
                     "consumer/conanfile.py": GenConanfile().with_requires("dep/0.1")})

        client.run("create dep dep/0.1@ -s build_type=Release")
        package_id = re.search(r"dep/0.1:(\S+)", str(client.out)).group(1)
        assert f"dep/0.1: Package '{package_id}' created" in client.out

        client.run("install consumer -s build_type=Debug")
        assert "dep/0.1: Main binary package '040ce2bd0189e377b2d15eb7246a4274d1c63317' missing. "\
               f"Using compatible package '{package_id}'" in client.out
