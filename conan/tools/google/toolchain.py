import json

from conan.tools import CONAN_TOOLCHAIN_ARGS_FILE
from conans.util.files import save


class BazelToolchain(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile

    def generate(self):
        bazel_config = self._conanfile.conf["tools.google.bazel:config"]
        bazelrc_path = self._conanfile.conf["tools.google.bazel:bazelrc_path"]

        save(CONAN_TOOLCHAIN_ARGS_FILE, json.dumps({
            "bazel_config": bazel_config,
            "bazelrc_path": bazelrc_path
        }))
