# coding=utf-8

import os
from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.client.run_environment import RunEnvironment


def write_toolchain(conanfile, path, output):
    if hasattr(conanfile, "toolchain"):
        assert callable(conanfile.toolchain), "toolchain should be a callable method"
        # This is the toolchain
        tc = conanfile.toolchain()
        tc.dump(path)

        # Run environment
        run_environment = RunEnvironment(conanfile).vars

        # Dump also files for the virtualenv
        venv = VirtualEnvGenerator(conanfile)
        venv.output_path = path

        for it_run, value in run_environment.items():
            if it_run in venv.env:
                venv.env[it_run] += value
            else:
                venv.env[it_run] = value

        for filename, content in venv.content.items():
            with open(os.path.join(path, filename), "w") as f:
                f.write(content)

# TODO: Generators, toolchain and environment, always, everytime you run `conan install`, maybe
# TODO: it is time for a folder `ConanFiles/` in the install directory. Also, from the generators,
# TODO: it should be possible/easy to infer the toolchain to generate:
# TODO:  * 'cmake' family: toolchain for cmake, environment
# TODO:  * 'IDE': only the environment to run the IDE (maybe set env and run IDE/version)
