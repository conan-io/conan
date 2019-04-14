import calendar
import os
import shutil
import time
from collections import OrderedDict

from conans.client.file_copier import FileCopier
from conans.model import Generator
from conans import ConanFile
from conans.model.manifest import FileTreeManifest
from conans.paths import BUILD_INFO_DEPLOY
from conans.util.files import mkdir, md5sum


class DeployGenerator(Generator):
    directory_dict = OrderedDict({"include_paths": "include",
                                  "src_paths": "src",
                                  "lib_paths": "lib",
                                  "res_paths": "res",
                                  "build_paths": "build"
                                  })

    @staticmethod
    def files(path):
        for file in os.listdir(path):
            if os.path.isfile(os.path.join(path, file)):
                yield file

    def to_directory_dir_name(self, directory_path_name):
        return self.directory_dict.get(directory_path_name)

    def deploy_manifest_content(self, copied_files):
        date = calendar.timegm(time.gmtime())
        file_dict = {}
        for f in copied_files:
            abs_path = os.path.join(self.output_path, f)
            file_dict[f] = md5sum(abs_path)
        manifest = FileTreeManifest(date, file_dict)
        return repr(manifest)

    @property
    def directory_path_names(self):
        return self.directory_dict.keys()

    @property
    def filename(self):
        return BUILD_INFO_DEPLOY

    @property
    def content(self):
        copied_files = []

        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            for directory_path in self.directory_path_names:
                if not getattr(dep_cpp_info, directory_path):
                    continue
                for path in getattr(dep_cpp_info, directory_path):
                    if os.path.normpath(path) == os.path.normpath(dep_cpp_info.rootpath):
                        # Copy only first level files of default value build_paths
                        for file in self.files(path):
                            if file in ["conaninfo.txt", "conanmanifest.txt"]:
                                continue
                            src = os.path.normpath(os.path.join(path, file))
                            dst = os.path.join(self.output_path, dep_name,
                                               self.to_directory_dir_name(directory_path), file)
                            mkdir(os.path.dirname(dst))
                            shutil.copyfile(src, dst)
                            copied_files.append(dst)
                    else:
                        if os.listdir(path):
                            src = os.path.normpath(path)
                            dst = os.path.join(self.output_path, dep_name,
                                               self.to_directory_dir_name(directory_path))
                            copier = FileCopier([src], dst)
                            copier("*")
                            copied_files.extend([os.path.join(dst, f) for f in copier._copied])
        return self.deploy_manifest_content(copied_files)
