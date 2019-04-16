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
        return ["include_paths", "src_paths", "lib_paths", "res_paths", "build_paths"]

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

                for root, _, files in os.walk(os.path.normpath(dep_cpp_info.rootpath)):
                    for f in files:
                        if f in ["conaninfo.txt", "conanmanifest.txt"]:
                            continue
                        src = os.path.normpath(os.path.join(root, f))
                        dst = os.path.join(self.output_path, dep_name,
                                           os.path.relpath(root, dep_cpp_info.rootpath), f)
                        dst = os.path.normpath(dst)
                        mkdir(os.path.dirname(dst))
                        shutil.copyfile(src, dst)
                        copied_files.append(dst)
        return self.deploy_manifest_content(copied_files)
