import os
import shutil
import zipfile
import tarfile

from conans.errors import ConanException
from conans.util import files
from conans import tools

class BinaryPacker(object):
    def __init__(self, name, version, user, channel, properties, package_dir, output_dir):
        self._name = name
        self._version = version
        self._user = user
        self._channel = channel
        self._properties = properties
        self._package_dir = package_dir
        self._output_dir = output_dir
        self._packname = ''

        self._os = properties['settings']['os']
        self._compiler = properties['settings']['compiler']
        self._compiler_version = properties['settings']['compiler.version']
        self._arch = properties['settings']['arch']
        #self._libcxx = self._settings.get_safe("compiler.libcxx")

        self._runtime = properties['settings']['compiler.runtime'] if 'compiler.runtime' in properties['settings'] else ''
        self._build_type = properties['settings']['build_type']
        self._link = 'shared' if properties['options']['shared'] else 'static'

        self.filename = self.construct_pack_name()


    def compress(self, output_file=None, src_stage_dir='packs', compression='zip', checksum=True):
        self._packing_dir = os.path.join(self._output_dir, src_stage_dir, self.filename)

        compression = compression.lstrip(".")
        print("Using compression: " + compression)

        # TODO: make add --force option for deleting existing pack destinations (?)
        if os.path.exists(self._packing_dir):
            #print("\nRemoving: " + self._packing_dir)
            shutil.rmtree(self._packing_dir)
            #print(self._packing_dir + " already exists. Remove first.")

        print("\nPacking in: " + self._packing_dir)

        print("\nCopying: " + self._package_dir)
        shutil.copytree(self._package_dir, self._packing_dir, symlinks=True)

        with tools.chdir(os.path.dirname(self._packing_dir)):

            target_archive = output_file + '.' + compression

            if compression == 'zip':
                self.zip(output_file, target_archive)
            elif compression == 'gz' or compression == 'bz2' or compression == 'xz':
                target_archive =  output_file + '.tar.' + compression
                self.tar(output_file, target_archive, compression=compression)
            else:
                raise ConanException("[%s] is not a supported compression filetype." % compression)

            print("Created: " + os.path.join(os.getcwd(), target_archive))

            # allow use to set this (?)
            if checksum:
                md5sum_file = '{0}.md5'.format(output_file)
                with open(md5sum_file, "w") as tf:
                    tf.write("{0} {1}".format(target_archive, files.md5sum(target_archive)))


    ''' this should go in tools.zip() actually '''
    def zip(self, src_dir=None, file=None):
        zipf = zipfile.ZipFile(file, 'w', zipfile.ZIP_DEFLATED)
        self.zipdir(src_dir, zipf)
        zipf.close()

    def zipdir(self, path, ziph):
        for root, dirs, files in os.walk(path):
            for file in files:
                ziph.write(os.path.join(root, file))

    def tar(self, src_dir=None, file=None, compression='gz'):
        try:
            with tarfile.open(file, "w:%s" % compression) as tar:
                tar.add(src_dir, arcname=os.path.basename(src_dir))
        except:
            raise ConanException("Cannot compress %s. Compression [%s] may not be supported by your Python." % (file,compression))


    @property
    def pack_dir(self):
        return self._pack_dir

    @property
    def os(self):
        if self._os == 'Windows':
            return 'win'
        if self._os == 'Linux':
            return 'lnx'
        if self._os == 'Macos':
            return 'osx'

        return self._os

    @property
    def arch(self):
        return self._arch

    @property
    def build_type(self):
        return self._build_type.lower()

    @property
    def compiler(self):
        if self._compiler == 'Visual Studio':
            return 'vs'
        else:
            return self._compiler

    @property
    def compiler_version(self):
        if self._compiler == "Visual Studio":
            _visuals = {'8': '2005',
                        '9': '2008',
                        '10': '2010',
                        '11': '2012',
                        '12': '2013',
                        '14': '2015',
                        '15': '2017'}
            return _visuals[self._compiler_version]

        return self._compiler_version

    @property
    def compiler_runtime(self):
        if self._compiler == "Visual Studio":
            return self._runtime
        else:
            return ''

    @property
    def build(self):
	build_type = self.build_type
        runtime = '-'+self.compiler_runtime if self.compiler_runtime else ''
        link = '-'+self._link if self._link else ''

        return '{build_type}{runtime}{link}'.format(build_type=build_type,
                                                    runtime=runtime,
                                                    link=link)


    def construct_pack_name(self):
        return '{name}-{version}-{os}-{arch}-{build}-{compiler}{compiler_version}'.format(name=self._name,
                                                                                          version=self._version,
                                                                                          os=self.os,
                                                                                          arch=self.arch,
                                                                                          build=self.build,
                                                                                          compiler=self.compiler,
                                                                                          compiler_version=self.compiler_version)

    @property
    def filename(self):
        return self._packname

    @filename.setter
    def filename(self, filename):
        self._packname = filename
