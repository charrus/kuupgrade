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
        self.kernels = self._get_kernels()

    def _get_arch(self):
        return apt_pkg.get_architectures()[0]
    
    def _get_kernels(self):
        kernels = {}
        rex = re.compile(r'<a href="([a-zA-Z0-9\-._\/]+)">([a-zA-Z0-9\-._]+)[\/]*<\/a>')

        # Get a list of installed linux-image packages
        pkg_list = PackageList()
        installed = pkg_list.get_versions('linux-image')

        r = requests.get(self.URI_KERNEL_UBUNTU_MAINLINE)

        # FIXME: Sort out if the key has the 'v' prefix or not
        # Should it also contain another version with or without
        # If the version without the 'v' prefix is in installed, then set entry['installed'] = 1
        for line in rex.findall(r.text):
            url = r.url + line[0]
            version = line[1]
            if version.startswith('v'):
                entry = { 'url': url + '/' + self.arch }
                version = version[1:]
                kernels[version] = entry

        return kernels

    def versions(self):
        versions = sorted(self.kernels.keys())
        return versions

    def get_kernel_urls(self, version):
        urls = []
        rex = re.compile(r'<a href="([a-zA-Z0-9\-._]+)">([a-zA-Z0-9\-._]+)<\/a>')
        rex_header = re.compile(r'linux-headers-[a-zA-Z0-9.\-_]*generic_[a-zA-Z0-9.\-]*_' + self.arch + r'.deb')
        rex_header_all = re.compile(r'linux-headers-[a-zA-Z0-9.\-_]*_all.deb')
        rex_image = re.compile('linux-image-[a-zA-Z0-9.\-_]*generic_([a-zA-Z0-9.\-]*)_' + self.arch + r'.deb')
        rex_image_extra = re.compile('linux-image-extra-[a-zA-Z0-9.\-_]*generic_[a-zA-Z0-9.\-]*_' + self.arch + r'.deb')
        rex_modules = re.compile('linux-modules-[a-zA-Z0-9.\-_]*generic_[a-zA-Z0-9.\-]*_' + self.arch + r'.deb')

        r = requests.get(self.kernels[version])

        for line in rex.findall(r.text):
            file_url = r.url + line[0]
            file_name = line[1]

            if rex_header.match(file_name):
                urls.append(file_url)
            elif rex_header_all.match(file_name):
                urls.append(file_url)
            elif rex_image.match(file_name):
                urls.append(file_url)
            elif rex_image_extra.match(file_name):
                urls.append(file_url)
            elif rex_modules.match(file_name):
                urls.append(file_url)
            else:
                continue

        return urls

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
    urls = kernel.get_kernel_urls('v5.7.12')

    pprint.pprint(urls)

    pkg_list = PackageList()

    versions = pkg_list.get_versions('linux-image')

    pprint.pprint(versions)
 
if __name__ == '__main__':
    main()
