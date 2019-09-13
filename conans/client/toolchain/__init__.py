# coding=utf-8

import os
from conans.client.generators.virtualenv import VirtualEnvGenerator


def write_toolchain(conanfile, path, output):
    if hasattr(conanfile, "toolchain"):
        assert callable(conanfile.toolchain), "toolchain should be a callable method"
        # This is the toolchain
        tc = conanfile.toolchain()
        tc.dump(path)

        # Dump also files for the virtualenv
        venv = VirtualEnvGenerator(conanfile)
        for filename, content in venv.content.items():
            with open(os.path.join(path, filename), "w") as f:
                f.write(content)
