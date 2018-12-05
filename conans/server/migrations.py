import os
import shutil

from conans import DEFAULT_REVISION_V1
from conans.migrations import Migrator
from conans.model.version import Version
from conans.paths import PACKAGES_FOLDER
from conans.util.files import list_folder_subdirs, mkdir, rmdir


class ServerMigrator(Migrator):

    def _make_migrations(self, old_version):
        # ############### FILL THIS METHOD WITH THE REQUIRED ACTIONS ##############

        # VERSION 0.1
        if old_version == Version("0.1"):
            # Remove config, conans, all!
            self.out.warn("Reseting configuration and storage files...")
            if self.conf_path:
                rmdir(self.conf_path)
            if self.store_path:
                rmdir(self.store_path)

        if old_version < Version("1.10.0"):
            if not os.path.exists(self.store_path) or not os.listdir(self.store_path):
                # Empty storage
                return
            try:
                self.migrate_to_revisions_layout()
            except Exception as e:
                print("An error ocurred during the migration, please restore the backup directory "
                      "and try again")
                print(e)
                exit(1)

        # ########################################################################

    def migrate_to_revisions_layout(self):
        # .conan/data/lib/1.0/user/channel/export/*
        # .conan/data/lib/1.0/user/channel/0/export/*

        # .conan/data/lib/1.0/user/channel/package/*
        # .conan/data/lib/1.0/user/channel/0/package/*

        # .conan/data/lib/1.0/user/channel/package/XXX/*
        # .conan/data/lib/1.0/user/channel/0/package/XXX/0/*
        from six.moves import input as raw_input
        print("**********************************************")
        print("*                                            *")
        print("*       STORAGE MIGRATION NEEDED!            *")
        print("*                                            *")
        print("**********************************************")
        a = raw_input("A migration of your storage is needed, please backup first the storage "
                      "directory before continue: \n\n'%s' \n\nContinue? Y/N " % self.store_path)
        print("**********************************************")

        if a.lower() != "y":
            print("Exiting...")
            exit(1)

        print("**********************************************")
        print("*                                            *")
        print("*       MIGRATION IN PROGRESS                *")
        print("*                                            *")
        print("**********************************************")
        subdirs = list_folder_subdirs(basedir=self.store_path, level=4)
        for subdir in subdirs:
            base_dir = os.path.join(self.store_path, subdir)
            for export_or_package in os.listdir(base_dir):
                the_dir = os.path.join(base_dir, export_or_package)
                dest_dir = os.path.join(base_dir, DEFAULT_REVISION_V1)
                mkdir(dest_dir)
                shutil.move(the_dir, dest_dir)
                print("Moving '%s': %s" % (subdir, export_or_package))

            packages_dir = os.path.join(self.store_path, subdir, DEFAULT_REVISION_V1, PACKAGES_FOLDER)

            if not os.path.exists(packages_dir):
                continue
            for pid in os.listdir(packages_dir):
                package_dir = os.path.join(packages_dir, pid)
                mkdir(os.path.join(package_dir, DEFAULT_REVISION_V1))
                print(" - Package '%s'" % pid)
                for item in os.listdir(package_dir):
                    if item == DEFAULT_REVISION_V1:
                        continue
                    origin_path = os.path.join(package_dir, item)
                    dest_path = os.path.join(package_dir, DEFAULT_REVISION_V1, item)
                    mkdir(dest_dir)
                    shutil.move(origin_path, dest_path)
        print("**********************************************")
        print("*                                            *")
        print("*       MIGRATION COMPLETED!                 *")
        print("*                                            *")
        print("**********************************************")
