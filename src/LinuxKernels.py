#!/usr/bin/python3

import requests
import re
import pprint
import apt_pkg
import multiprocessing as mp
import subprocess

class LinuxKernel:
    """A Kernel on mainline"""

    def __init__(self, version, arch, url):
        self.url = url
        self.version = version
        self.arch = arch
        self.deb_version = None

        rex = re.compile(r'<a href="([a-zA-Z0-9\-._\/]+)">([a-zA-Z0-9\-._\/]+)<\/a>')
        rex_header = re.compile(r'[a-zA-Z0-9\-._\/]*linux-headers-[a-zA-Z0-9.\-_]*generic_[a-zA-Z0-9.\-]*_' + self.arch + r'.deb')
        rex_header_all = re.compile(r'[a-zA-Z0-9\-._\/]*linux-headers-[a-zA-Z0-9.\-_]*_all.deb')
        rex_image = re.compile(r'[a-zA-Z0-9\-._\/]*linux-image-[a-zA-Z0-9.\-_]*generic_([a-zA-Z0-9.\-]*)_' + self.arch + r'.deb')
        rex_image_extra = re.compile(r'[a-zA-Z0-9\-._\/]*linux-image-extra-[a-zA-Z0-9.\-_]*generic_[a-zA-Z0-9.\-]*_' + self.arch + r'.deb')
        rex_modules = re.compile(r'[a-zA-Z0-9\-._\/]*linux-modules-[a-zA-Z0-9.\-_]*generic_[a-zA-Z0-9.\-]*_' + self.arch + r'.deb')

        # Extract the urls for our architecture
        # Especially for the all debs, these are listed multiple times
        # per architecture, so use a dict to make them unique
        urls = {}

        # Grab the version page
        rver = requests.get(url)
        # The version can be extracted from the .deb filenames
        deb_versions = rex_image.findall(rver.text)
        # If we can't extract the version, then skip it
        if not deb_versions:
            return None
        self.deb_version = deb_versions[0]

        for debs in rex.findall(rver.text):
            # First group is the uri - so add the base url
            file_url = rver.url + debs[0]
            # Second group is the embedded version in the deb filename
            file_name = debs[1]

            if rex_header.match(file_name):
                urls[file_url] = 1
            elif rex_header_all.match(file_name):
                urls[file_url] = 1
            elif rex_image.match(file_name):
                urls[file_url] = 1
            elif rex_image_extra.match(file_name):
                urls[file_url] = 1
            elif rex_modules.match(file_name):
                urls[file_url] = 1
            else:
                continue

        self.urls = list(urls.keys())

    def __str__(self):
        return self.version

class LinuxKernels:
    """All Kernel on mainline"""

    URI_KERNEL_UBUNTU_MAINLINE = 'http://kernel.ubuntu.com/~kernel-ppa/mainline/'
    NUM_WORKERS = 16

    def __init__(self):
        self.kernels = []
        pkg_list = PackageList()
        self.installed = pkg_list.get_versions('linux-image')

    def __iter__(self):
        return LinuxKernelsIterator(self)

    def init(self):
        apt_pkg.init()
        self.arch = self._get_arch()
        rex_index = re.compile(r'<a href="(v[a-zA-Z0-9\-._]+\/)">([a-zA-Z0-9\-._]+)\/<\/a>')
        result = subprocess.run(['uname', '-r'], stdout=subprocess.PIPE)
        self.running_kernel = result.stdout.decode()
        r = requests.get(self.URI_KERNEL_UBUNTU_MAINLINE)

        # Create a queue to submit requests for each version
        self.query_queue = mp.Queue()
        self.result_queue = mp.Queue()

        # Attach a process to each worker and start it
        self.workers = [
            mp.Process(
                target=self.add_version, args=(self.query_queue,self.result_queue)
            )
            for _ in range(self.NUM_WORKERS)
        ]
        for worker in self.workers:
            worker.start()

        num_jobs = 0

        # Iterate through all the versions and add them to the queue
        for line in rex_index.findall(r.text):
            url = r.url + line[0]
            version = line[1]
            self.query_queue.put({ 'url': url, 'version': version})

        # Stop all the workers
        for _ in range(self.NUM_WORKERS):
            self.query_queue.put('STOP')

        remaining = self.NUM_WORKERS

        while True:
            result = self.result_queue.get()
            if result == 'STOP':
                remaining -= 1
                if remaining == 0:
                    break
                else:
                    continue
            self.kernels.append(result)
        
    def _get_arch(self):
        return apt_pkg.get_architectures()[0]
    
    def add_version(self, query_queue, result_queue):
        while True:
            new_version = query_queue.get()
            if new_version == 'STOP':
                result_queue.put('STOP')
                break

            url = new_version['url']
            version = new_version['version']

            kernel = LinuxKernel(version=new_version['version'],
                                 arch=self.arch,
                                 url=new_version['url'])
            if(kernel):
                kernel.installed = kernel.deb_version in self.installed
                kernel.running = kernel.deb_version == self.running_kernel
                result_queue.put(kernel)

class LinuxKernelsIterator:
    def __init__(self, kernels):
        self._kernels = kernels
        self._index = 0

    def __next__(self):
        if self._index < len(self._kernels.kernels):
            kernel = self._kernels.kernels[self._index]
            self._index += 1
            return kernel

        raise StopIteration

class PackageList:
    """ Represents a list of installed packages """

    def __init__(self):
        self.packages = self.installed_packages()

    def installed_packages(self):
        packages = {}
        result = subprocess.run(['dpkg', '-l'], stdout=subprocess.PIPE)

        for dpkg in result.stdout.decode('utf-8').splitlines():
            fields = dpkg.split()
            if len(fields) < 5:
                continue
            status = fields[0]
            name = fields[1]
            version = fields[2]
            if status != 'ii':
                continue
            pkg_id = name + '|' + version
            packages[pkg_id] = { 'name': name, 'version': version }

        return packages

    def get_versions(self, name):
        versions = []
        for pkg_id in self.packages.keys():
            if pkg_id.startswith(name):
                versions.append(self.packages[pkg_id]['version'])
        return versions
