#!/usr/bin/python3

import requests
import re
import pprint
import apt_pkg

class LinuxKernel:
    """A Kernel on mainline"""

    URI_KERNEL_UBUNTU_MAINLINE = 'http://kernel.ubuntu.com/~kernel-ppa/mainline/'

    def __init__(self):
        apt_pkg.init()
        self.arch = self._get_arch()
        self.init_res()
        self.kernels = self._init_kernels()

    def _get_arch(self):
        return apt_pkg.get_architectures()[0]
    
    def init_res(self):
        self.rex_index = re.compile(r'<a href="([a-zA-Z0-9\-._\/]+)">([a-zA-Z0-9\-._]+)[\/]*<\/a>')
        self.rex = re.compile(r'<a href="([a-zA-Z0-9\-._\/]+)">([a-zA-Z0-9\-._\/]+)<\/a>')
        self.rex_header = re.compile(r'[a-zA-Z0-9\-._\/]*linux-headers-[a-zA-Z0-9.\-_]*generic_[a-zA-Z0-9.\-]*_' + self.arch + r'.deb')
        self.rex_header_all = re.compile(r'[a-zA-Z0-9\-._\/]*linux-headers-[a-zA-Z0-9.\-_]*_all.deb')
        self.rex_version = re.compile(r'[a-zA-Z0-9\-._\/]*linux-image-[a-zA-Z0-9.\-_]*generic_([a-zA-Z0-9.\-]*)_' + self.arch + r'.deb')
        self.rex_image = re.compile(r'[a-zA-Z0-9\-._\/]*linux-image-[a-zA-Z0-9.\-_]*generic_([a-zA-Z0-9.\-]*)_' + self.arch + r'.deb')
        self.rex_image_extra = re.compile(r'[a-zA-Z0-9\-._\/]*linux-image-extra-[a-zA-Z0-9.\-_]*generic_[a-zA-Z0-9.\-]*_' + self.arch + r'.deb')
        self.rex_modules = re.compile(r'[a-zA-Z0-9\-._\/]*linux-modules-[a-zA-Z0-9.\-_]*generic_[a-zA-Z0-9.\-]*_' + self.arch + r'.deb')

    def _init_kernels(self):
        kernels = {}

        # Get a list of installed linux-image packages
        pkg_list = PackageList()
        installed = pkg_list.get_versions('linux-image')

        r = requests.get(self.URI_KERNEL_UBUNTU_MAINLINE)

        # FIXME: Sort out if the key has the 'v' prefix or not
        # Should it also contain another version with or without
        # If the version without the 'v' prefix is in installed, then set entry['installed'] = 1
        for line in self.rex_index.findall(r.text):
            url = r.url + line[0]
            version = line[1]
            if version.startswith('v'):
                entry = {}
                rver = requests.get(url)

                real_versions = self.rex_version.findall(rver.text)
                if not real_versions:
                    continue
                entry['url'] = url
                entry['version'] = real_versions[0]
                entry['urls'] = []
                entry['installed'] = real_versions[0] in installed
                kernels[version] = entry

        return kernels

    def versions(self):
        versions = sorted(self.kernels.keys())
        return versions

    def _get_kernel_urls(self, url):
        urls_dict = {}

        r = requests.get(url)

        for line in self.rex.findall(r.text):
            file_url = r.url + line[0]
            file_name = line[1]

            if self.rex_header.match(file_name):
                urls_dict[file_url] = 1
            elif self.rex_header_all.match(file_name):
                urls_dict[file_url] = 1
            elif self.rex_image.match(file_name):
                urls_dict[file_url] = 1
            elif self.rex_image_extra.match(file_name):
                urls_dict[file_url] = 1
            elif self.rex_modules.match(file_name):
                urls_dict[file_url] = 1
            else:
                continue

        return list(urls_dict.keys())

    def get_kernel(self, version):
        #self.kernels[version]['urls'] = self._get_kernel_urls(self.kernels[version]['url'])
        kernel = self.kernels[version]
        kernel['urls'] = self._get_kernel_urls(kernel['url'])

        return kernel

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

    kernel = LinuxKernel()
    versions = kernel.versions()
    pprint.pprint(versions)
    kernel = kernel.get_kernel('v5.6.19')

    pprint.pprint(kernel)

    #pkg_list = PackageList()

    #versions = pkg_list.get_versions('linux-image')

    #pprint.pprint(versions)
 
if __name__ == '__main__':
    main()
