from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.util.files import rmdir
import shutil
from conans.errors import ConanException


class PackageCopier(object):
    """ Class responsible for copying or moving packages from users/channels """

    def __init__(self, paths, user_io):
        self._user_io = user_io
        self._paths = paths

    def copy(self, reference, package_ids, username, channel, force=False):
        assert(isinstance(reference, ConanFileReference))
        dest_ref = "%s/%s@%s/%s" % (reference.name, reference.version, username, channel)
        dest_ref = ConanFileReference.loads(dest_ref)
        # Copy export
        export_origin = self._paths.export(reference)
        if not os.path.exists(export_origin):
            raise ConanException("'%s' doesn't exist" % str(reference))
        export_dest = self._paths.export(dest_ref)
        if os.path.exists(export_dest):
            if not force and not self._user_io.request_boolean("'%s' already exist. Override?"
                                                               % str(reference)):
                return
            rmdir(export_dest)
        shutil.copytree(export_origin, export_dest)
        self._user_io.out.info("Copied %s to %s" % (str(reference), str(dest_ref)))

        # Copy packages
        for package_id in package_ids:
            package_origin = PackageReference(reference, package_id)
            package_dest = PackageReference(dest_ref, package_id)
            package_path_origin = self._paths.package(package_origin)
            package_path_dest = self._paths.package(package_dest)
            if os.path.exists(package_path_dest):
                if not force and not self._user_io.request_boolean("Package '%s' already exist."
                                                                   " Override?"
                                                                   % str(package_id)):
                    continue
                rmdir(package_path_dest)
            shutil.copytree(package_path_origin, package_path_dest)
            self._user_io.out.info("Copied %s to %s" % (str(package_id), str(dest_ref)))
