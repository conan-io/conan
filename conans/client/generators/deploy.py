import os
import shutil
from collections import OrderedDict

from conans.model import Generator
from conans import ConanFile
from conans.paths import BUILD_INFO_DEPLOY


class DeployGenerator(Generator):
    self.directory_dict = OrderedDict({"include_paths": "include",
                                       "src_paths": "src",
                                       "lib_paths": "lib",
                                       "res_paths": "res",
                                       "build_paths": "build"
                                       })

    def files(path):
        for file in os.listdir(path):
            if os.path.isfile(os.path.join(path, file)):
                yield file

    def to_directory_dir_name(self, directory_path_name):
        return self.directory_dict.get(directory_path_name)

    @pproperty
    def directory_path_names(self):
        return self.directory_dict.keys()

    @property
    def filename(self):
        return BUILD_INFO_DEPLOY

    @property
    def content(self):
        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            for key in self.directory_path_names:
                if getattr(dep_cpp_info, key):
                    for path in getattr(dep_cpp_info, key):
                        if path == dep_cpp_info.sysroot:  # Copy only first level files
                            for file in self.files(path):
                                src = os.path.normpath(os.path.join(path, file))
                                dst = os.path.join(self.output_path, dep_name, file)
                                shutil.copyfile(src, dst)
                        if os.listdir(path):
                            src = os.path.normpath(path)
                            dir_name = os.path.basename(path)
                            dst = os.path.join(self.output_path, dep_name, dir_name)
                            shutil.copytree(src, dst)
        return "Files deployed!"
