#!/usr/bin/python3

import requests
import re
import pprint
import apt_pkg
import multiprocessing as mp

class LinuxKernels:
    """A Kernel on mainline"""

    URI_KERNEL_UBUNTU_MAINLINE = 'http://kernel.ubuntu.com/~kernel-ppa/mainline/'
    NUM_WORKERS = 8

    def __init__(self):
        self.kernels = {}
        pkg_list = PackageList()
        self.installed = pkg_list.get_versions('linux-image')

    def init(self):
        apt_pkg.init()
        self.arch = self._get_arch()
        self.init_regexes()
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
        for line in self.rex_index.findall(r.text):
            url = r.url + line[0]
            version = line[1]
            self.query_queue.put({ 'url': url, 'version': version})
            num_jobs += 1

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
            version = result['version']
            data = result['data']
            self.kernels[version] = data

        
    def _get_arch(self):
        return apt_pkg.get_architectures()[0]
    
    def init_regexes(self):
        self.rex_index = re.compile(r'<a href="([a-zA-Z0-9\-._\/]+)">([a-zA-Z0-9\-._]+)[\/]*<\/a>')
        self.rex = re.compile(r'<a href="([a-zA-Z0-9\-._\/]+)">([a-zA-Z0-9\-._\/]+)<\/a>')
        self.rex_header = re.compile(r'[a-zA-Z0-9\-._\/]*linux-headers-[a-zA-Z0-9.\-_]*generic_[a-zA-Z0-9.\-]*_' + self.arch + r'.deb')
        self.rex_header_all = re.compile(r'[a-zA-Z0-9\-._\/]*linux-headers-[a-zA-Z0-9.\-_]*_all.deb')
        self.rex_image = re.compile(r'[a-zA-Z0-9\-._\/]*linux-image-[a-zA-Z0-9.\-_]*generic_([a-zA-Z0-9.\-]*)_' + self.arch + r'.deb')
        self.rex_image_extra = re.compile(r'[a-zA-Z0-9\-._\/]*linux-image-extra-[a-zA-Z0-9.\-_]*generic_[a-zA-Z0-9.\-]*_' + self.arch + r'.deb')
        self.rex_modules = re.compile(r'[a-zA-Z0-9\-._\/]*linux-modules-[a-zA-Z0-9.\-_]*generic_[a-zA-Z0-9.\-]*_' + self.arch + r'.deb')

    def add_version(self, query_queue, result_queue):
        while True:
            new_version = query_queue.get()
            if new_version == 'STOP':
                result_queue.put('STOP')
                break

            url = new_version['url']
            version = new_version['version']
            entry = {}

            # Extract the urls for our architecture
            # Especially for the all debs, these are listed multiple times
            # per architecture, so use a dict to make them unique
            urls = {}

            # Grab the version page
            rver = requests.get(url)
            # The version can be extracted from the .deb filenames
            deb_versions = self.rex_index.findall(rver.text)
            # If we can't extract the version, then skip it
            if not deb_versions:
                continue
            deb_version = deb_versions[0]

            for debs in self.rex.findall(rver.text):
                # First group is the uri - so add the base url
                file_url = rver.url + debs[0]
                # Second group is the embedded version in the deb filename
                file_name = debs[1]

                if self.rex_header.match(file_name):
                    urls[file_url] = 1
                elif self.rex_header_all.match(file_name):
                    urls[file_url] = 1
                elif self.rex_image.match(file_name):
                    urls[file_url] = 1
                    deb_version = deb_versions[0]
                elif self.rex_image_extra.match(file_name):
                    urls[file_url] = 1
                elif self.rex_modules.match(file_name):
                    urls[file_url] = 1
                else:
                    continue

            entry['urls'] = list(urls.keys())
            entry['url'] = url
            entry['version'] = deb_version
            entry['installed'] = deb_version in self.installed
            result_queue.put({ 'version': version, 'data': entry})

    def versions(self):
        versions = sorted(self.kernels.keys())
        return versions

    def get_kernel(self, version):
        return self.kernels[version]


class Package:
    """ Represents a package """

    def __init__(self, name, version):
        self.name = name
        self.version = version

class PackageList:
    """ Represents a list of installed packages """

    def __init__(self):
        self.packages = self.installed_packages()

    def installed_packages(self):
        import subprocess

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
            packages[pkg_id] = Package(name, version)

        return packages

    def get_versions(self, name):
        versions = []
        for pkg_id in self.packages.keys():
            if pkg_id.startswith(name):
                versions.append(self.packages[pkg_id].version)
        return versions

def main():
    import pprint

    kernel = LinuxKernels()
    kernel.init()
    versions = kernel.versions()
    pprint.pprint(versions)
    kernel = kernel.get_kernel('v5.6.19')

    pprint.pprint(kernel)

    #pkg_list = PackageList()

    #versions = pkg_list.get_versions('linux-image')

    #pprint.pprint(versions)
 
if __name__ == '__main__':
    main()
