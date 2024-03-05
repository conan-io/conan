import os
import json
from io import BytesIO
import textwrap
import shutil
import docker

from conan.api.model import ListPattern
from conan.api.output import ConanOutput
from conan.api.conan_api import ConfigAPI


class DockerRunner:

    def __init__(self, conan_api, command, profile, args, raw_args):
        self.conan_api = conan_api
        self.args = args
        self.raw_args = raw_args
        self.docker_client = docker.from_env()
        self.docker_api = docker.APIClient()
        self.command = command
        self.dockerfile = str(profile.runner.get('dockerfile', ''))
        self.image = str(profile.runner.get('image', 'conanrunner'))
        self.name = f'conan-runner-{profile.runner.get("suffix", "docker")}'
        self.remove = int(profile.runner.get('remove', 1))
        self.cache = str(profile.runner.get('cache', 'clean'))
        self.runner_home = os.path.join(args.path, '.conanrunner')
        self.container = None

    def run(self):
        """
        run conan inside a Docker continer
        """
        ConanOutput().title(msg=f'Building the Docker image: {self.image}')
        self.build_image()
        volumes, environment = self.create_runner_environment()
        try:
            if self.docker_client.containers.list(all=True, filters={'name': self.name}):
                self.container = self.docker_client.containers.get(self.name)
                self.container.start()
            else:
                self.container = self.docker_client.containers.run(self.image,
                                                                   "/bin/bash -c 'while true; do sleep 30; done;'",
                                                                   name=self.name,
                                                                   volumes=volumes,
                                                                   environment=environment,
                                                                   detach=True,
                                                                   auto_remove=False)
                self.init_container()
            self.run_command(' '.join([f'conan {self.command}'] + self.raw_args))
            self.update_local_cache()
        except:
            pass
        finally:
            if self.container:
                self.container.stop()
                if self.remove:
                    self.container.remove()

    def build_image(self):
        docker_build_logs = None
        if self.dockerfile:
            docker_build_logs = self.docker_api.build(path=self.dockerfile, tag=self.image)
        else:
            dockerfile = textwrap.dedent("""
                FROM ubuntu
                RUN apt update && apt upgrade -y
                RUN apt install -y build-essential
                RUN apt install -y python3-pip cmake git
                RUN cd /root && git clone https://github.com/davidsanfal/conan.git conan-io
                RUN cd /root/conan-io && pip install docker && pip install -e .
                """)

            docker_build_logs = self.docker_api.build(fileobj=BytesIO(dockerfile.encode('utf-8')),
                                                      nocache=False,
                                                      tag=self.image)
        for chunk in docker_build_logs:
            for line in chunk.decode("utf-8").split('\r\n'):
                if line:
                    stream = json.loads(line).get('stream')
                    if stream:
                        ConanOutput().info(stream.strip())

    def run_command(self, command, log=True):
        try:
            exec_stream = self.container.exec_run(f'/bin/bash -c \'{command}\'', stream=True, tty=True)
            while True:
                output = next(exec_stream.output)
                if log:
                    ConanOutput().info(output.decode('utf-8', errors='ignore').strip())
        except StopIteration:
            pass

    def create_runner_environment(self):
        volumes = {self.args.path: {'bind': self.args.path, 'mode': 'rw'}}
        environment = {'CONAN_RUNNER_ENVIRONMENT': '1'}
        if self.cache == 'shared':
            volumes[ConfigAPI(self.conan_api).home()] = {'bind': '/root/.conan2', 'mode': 'rw'}
        if self.cache in ['clean', 'copy']:
            shutil.rmtree(self.runner_home, ignore_errors=True)
            os.mkdir(self.runner_home)
            shutil.copytree(os.path.join(ConfigAPI(self.conan_api).home(), 'profiles'), os.path.join(self.runner_home, 'profiles'))
            if self.cache == 'copy':
                tgz_path = os.path.join(self.runner_home, 'conan_cache_save.tgz')
                self.conan_api.cache.save(self.conan_api.list.select(ListPattern("*:*")), tgz_path)
        return volumes, environment

    def init_container(self):
        if self.cache != 'shared':
            self.run_command('mkdir -p ${HOME}/.conan2/profiles', log=False)
            self.run_command('cp -r '+self.args.path+'/.conanrunner/profiles/. ${HOME}/.conan2/profiles/.', log=False)
            if self.cache in ['copy', 'clean']:
                self.run_command('conan cache restore '+self.args.path+'/.conanrunner/conan_cache_save.tgz')

    def update_local_cache(self):
        if self.cache != 'shared':
            self.run_command('conan cache save "*:*" --file '+self.args.path+'/.conanrunner/conan_cache_docker.tgz')
            tgz_path = os.path.join(self.runner_home, 'conan_cache_docker.tgz')
            ConanOutput().subtitle(msg=f'Copy conan cache from runner')
            package_list = self.conan_api.cache.restore(tgz_path)
