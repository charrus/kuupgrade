#!/usr/bin/python3

import argparse

from LinuxKernels import LinuxKernels

parser = argparse.ArgumentParser(description='Upgrade ubuntu kernel')
parser.add_argument('--list', action='store_true', default=True, help='List available kernels')
args = parser.parse_args()

print("Initializing...")
kernels = LinuxKernels()
kernels.init()
print("Done.")

if args.list:
    for kernel in kernels:
        running = ""
        installed = ""

        if kernel.valid:
            if kernel.running:
                running = "[Running]"
            if kernel.installed:
                installed = "[Installed]"
            version = kernel.version

            print(f'{version:10} {running} {installed}');

