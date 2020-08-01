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
        self.arch = self.get_arch()
        self.kernels = self.get_kernels()

    def get_arch(self):
        return apt_pkg.get_architectures()[0]
    
    def get_kernels(self):
        kernels = {}
        rex = re.compile(r'<a href="([a-zA-Z0-9\-._\/]+)">([a-zA-Z0-9\-._]+)[\/]*<\/a>')

        r = requests.get(self.URI_KERNEL_UBUNTU_MAINLINE)

        for line in rex.findall(r.text):
            url = r.url + line[0]
            version = line[1]
            kernels[version] = url + '/' + self.arch

        return kernels

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



def main():
    import pprint

    kernel = LinuxKernel()
    urls = kernel.get_kernel_urls('v5.7.12')

    pprint.pprint(urls)
 
if __name__ == '__main__':
    main()
