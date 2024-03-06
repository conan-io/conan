import os
import json
from io import BytesIO
import textwrap
import shutil
from conan.api.model import ListPattern
from conan.api.output import ConanOutput
from conan.api.conan_api import ConfigAPI
from conan.cli import make_abs_path
from conans.client.profile_loader import ProfileLoader
from conans.errors import ConanException


def docker_info(msg):
    ConanOutput().highlight('\n┌'+'─'*(2+len(msg))+'┐')
    ConanOutput().highlight(f'| {msg} |')
    ConanOutput().highlight('└'+'─'*(2+len(msg))+'┘\n')


def list_patterns(cache_info):
    _pattern = []
    for reference, info in cache_info.items():
        for revisions in info.get('revisions', {}).values():
            for package in revisions.get('packages').keys():
                _pattern.append(f'{reference}:{package}')
    return _pattern


class DockerRunner:
    def __init__(self, conan_api, command, profile, args, raw_args):
        import docker
        try:
            self.docker_client = docker.from_env()
            self.docker_api = docker.APIClient()
        except:
            raise ConanException("Docker Client failed to initialize. Check if it is installed and running")
        self.conan_api = conan_api
        self.args = args
        self.abs_host_path = make_abs_path(args.path)
        if args.format:
            raise ConanException("format argument is forbidden if running in a docker runner")
        self.abs_runner_home_path = os.path.join(self.abs_host_path, '.conanrunner')
        self.abs_docker_path = os.path.join('/root/conanrunner', os.path.basename(self.abs_host_path)).replace("\\","/")
        raw_args[raw_args.index(args.path)] = f'"{self.abs_docker_path}"'
        self.command = ' '.join([f'conan {command}'] + raw_args + ['-f json > create.json'])
        self.dockerfile = profile.runner.get('dockerfile')
        self.image = profile.runner.get('image')
        if not (self.dockerfile or self.image):
            raise ConanException("dockerfile path or docker image name is needed")
        self.image = self.image or 'conan-runner-default'
        self.name = f'conan-runner-{profile.runner.get("suffix", "docker")}'
        self.remove = int(profile.runner.get('remove', 1))
        self.cache = str(profile.runner.get('cache', 'clean'))
        self.container = None

    def run(self):
        """
        run conan inside a Docker continer
        """
        docker_info(f'Building the Docker image: {self.image}')
        self.build_image()
        volumes, environment = self.create_runner_environment()
        docker_info('Creating the docker container')
        try:
            if self.docker_client.containers.list(all=True, filters={'name': self.name}):
                self.container = self.docker_client.containers.get(self.name)
                self.container.start()
            else:
                self.container = self.docker_client.containers.run(
                    self.image,
                    "/bin/bash -c 'while true; do sleep 30; done;'",
                    name=self.name,
                    volumes=volumes,
                    environment=environment,
                    detach=True,
                    auto_remove=False)
                self.init_container()
            self.run_command(self.command)
            self.update_local_cache()
        except:
            ConanOutput().error(f'Something went wrong running "{self.command}" inside the container')
        finally:
            if self.container:
                docker_info('Stopping container')
                self.container.stop()
                if self.remove:
                    docker_info('Removing container')
                    self.container.remove()

    def build_image(self):
        if self.dockerfile:
            docker_build_logs = self.docker_api.build(path=self.dockerfile, tag=self.image)
            for chunk in docker_build_logs:
                for line in chunk.decode("utf-8").split('\r\n'):
                    if line:
                        stream = json.loads(line).get('stream')
                        if stream:
                            ConanOutput().info(stream.strip())

    def run_command(self, command, log=True, stream=True, tty=True):
        if log:
            docker_info(f'Running in container: "{command}"')
        exec_run = self.container.exec_run(f"/bin/bash -c '{command}'", stream=stream, tty=tty)
        if stream:
            try:
                while True:
                    chunk = next(exec_run.output).decode('utf-8', errors='ignore').strip()
                    if log:
                        ConanOutput().info(chunk)
            except StopIteration:
                pass
        else:
            return exec_run.output.decode('utf-8', errors='ignore').strip()

    def create_runner_environment(self):
        volumes = {self.abs_host_path: {'bind': self.abs_docker_path, 'mode': 'rw'}}
        environment = {'CONAN_RUNNER_ENVIRONMENT': '1'}
        if self.cache == 'shared':
            volumes[ConfigAPI(self.conan_api).home()] = {'bind': '/root/.conan2', 'mode': 'rw'}
        if self.cache in ['clean', 'copy']:
            shutil.rmtree(self.abs_runner_home_path, ignore_errors=True)
            os.mkdir(self.abs_runner_home_path)
            os.mkdir(os.path.join(self.abs_runner_home_path, 'profiles'))
            for file_name in ['global.conf', 'settings.yml', 'remotes.json']:
                src_file = os.path.join(ConfigAPI(self.conan_api).home(), file_name)
                if os.path.exists(src_file):
                    shutil.copy(src_file, os.path.join(self.abs_runner_home_path, file_name))
            self._copy_profiles(self.args.profile_build)
            self._copy_profiles(self.args.profile_host)
            if self.cache == 'copy':
                tgz_path = os.path.join(self.abs_runner_home_path, 'local_cache_save.tgz')
                docker_info(f'Save host cache in: {tgz_path}')
                self.conan_api.cache.save(self.conan_api.list.select(ListPattern("*:*")), tgz_path)
        return volumes, environment

    def init_container(self):
        if self.cache != 'shared':
            self.run_command('mkdir -p ${HOME}/.conan2/profiles', log=False)
            self.run_command('cp -r "'+self.abs_docker_path+'/.conanrunner/profiles/." ${HOME}/.conan2/profiles/.', log=False)
            for file_name in ['global.conf', 'settings.yml', 'remotes.json']:
                if os.path.exists( os.path.join(self.abs_runner_home_path, file_name)):
                    self.run_command('cp "'+self.abs_docker_path+'/.conanrunner/'+file_name+'" ${HOME}/.conan2/'+file_name, log=False)
            if self.cache in ['copy', 'clean']:
                self.run_command('conan cache restore "'+self.abs_docker_path+'/.conanrunner/local_cache_save.tgz"')

    def update_local_cache(self):
        if self.cache != 'shared':
            self.run_command('conan list --graph=create.json --graph-binaries=build --format=json > pkglist.json')
            self.run_command('conan cache save --list=pkglist.json --file "'+self.abs_docker_path+'"/.conanrunner/docker_cache_save.tgz')
            tgz_path = os.path.join(self.abs_runner_home_path, 'docker_cache_save.tgz')
            docker_info(f'Restore host cache from: {tgz_path}')
            package_list = self.conan_api.cache.restore(tgz_path)

    def _copy_profiles(self, profiles):
        cwd = os.getcwd()
        if profiles:
            for profile in profiles:
                profile_path = ProfileLoader.get_profile_path(os.path.join(ConfigAPI(self.conan_api).home(), 'profiles'), profile, cwd)
                shutil.copy(profile_path, os.path.join(self.abs_runner_home_path, 'profiles', os.path.basename(profile_path)))