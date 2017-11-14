import os
import zipfile
import tarfile

from conans.model.conan_file import ConanFile
from conans.model.settings import Settings
from conans.errors import ConanException
from conans.util import files
from conans import tools

class Deployment(object):
    def __init__(self, settings_or_conanfile):
        if isinstance(settings_or_conanfile, ConanFile):
            self._settings = settings_or_conanfile.settings
            self._conanfile = settings_or_conanfile
            #self.configure = self._configure_new
            #self.build = self._build_new
        else:
            raise ConanException("First parameter of Deployment() has to be a ConanFile instance.")

        self._copied_package = False

        self._link = 'shared' if self._conanfile.options.shared else 'static'

        self._os = self._settings.get_safe("os")
        self._compiler = self._settings.get_safe("compiler")
        self._compiler_version = self._settings.get_safe("compiler.version")
        self._arch = self._settings.get_safe("arch")
        self._op_system_version = self._settings.get_safe("os.version")
        self._libcxx = self._settings.get_safe("compiler.libcxx")
        self._runtime = self._settings.get_safe("compiler.runtime")
        self._build_type = self._settings.get_safe("build_type")

        super(Deployment, self).__init__()

        self._name = self._settings.get_safe("name")
        self._version = self._settings.get_safe("version")

        self.filename = self.build_deployment_name()


    def compress(self, output_file=None, src_stage_dir='artifacts', compression='zip', checksum=True):
        self._deployment_dir = os.path.join(src_stage_dir, self.filename)
        if not os.path.exists(self._deployment_dir):
            os.makedirs(self._deployment_dir)

        self._conanfile.copy("*", dst=self._deployment_dir)
        self._copied_package = True

        #self._conanfile.output.warn("Compressing: %s" % src_dir)
        #self._conanfile.output.warn("Archive: %s" % output_file)

        with tools.chdir(os.path.dirname(self._deployment_dir)):
            if compression == '.zip':
                self.zip(output_file, output_file + compression)
            elif compression == '.gz' or compression == '.bz2' or compression == '.xz':
                self.tar(output_file, output_file + compression, compression=compression[1:])
            else:
                raise ConanException("[%s] is not a supported compression filetype." % compression)

            if checksum:
                md5sum_file = '{0}.md5'.format(output_file)
                with open(md5sum_file, "w") as tf:
                    tf.write("{0} {1}".format(output_file + compression, files.md5sum(output_file + compression)))

    ''' this should go in tools.zip() actually '''
    def zip(self, src_dir=None, file=None):
        zipf = zipfile.ZipFile(file, 'w', zipfile.ZIP_DEFLATED)
        self.zipdir(src_dir, zipf)
        zipf.close()

    def zipdir(self, path, ziph):
        # ziph is zipfile handle
        for root, dirs, files in os.walk(path):
            for file in files:
                ziph.write(os.path.join(root, file))

    def tar(self, src_dir=None, file=None, compression='gz'):
        with tarfile.open(file, "w:%s" % compression) as tar:
            tar.add(src_dir, arcname=os.path.basename(src_dir))



    @property
    def deployment_dir(self):
        return self._deployment_dir

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

        return ''

    @property
    def compiler_runtime(self):
        if self._compiler == "Visual Studio":
            return self._runtime
        else:
            return ''

    @property
    def build(self):
        if self._compiler == "Visual Studio":
            return '{build_type}-{runtime}-{link}'.format(build_type=self.build_type,
                                                          runtime=self.compiler_runtime,
                                                          link=self._link)

        else:
            return ''


    def build_deployment_name(self):
        return '{name}-{version}-{os}-{arch}-{build}-{compiler}{compiler_version}'.format(name=self._conanfile.name,
                                                                                          version=self._conanfile.version,
                                                                                          os=self.os,
                                                                                          arch=self.arch,
                                                                                          build=self.build,
                                                                                          compiler=self.compiler,
                                                                                          compiler_version=self.compiler_version)

    @property
    def filename(self):
        return self._deployment_name

    @filename.setter
    def filename(self, filename):
        self._deployment_name = filename