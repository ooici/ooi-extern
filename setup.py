#!/usr/bin/env python

try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

import os
import sys

# Add /usr/local/include to the path for macs, fixes easy_install for several packages (like gevent and pyyaml)
if sys.platform == 'darwin':
    os.environ['C_INCLUDE_PATH'] = '/usr/local/include'


setup(  name = 'ooi-extern',
    version = '3.0.0',
    description = 'OOI Network Externalization services',
    url = '',
    download_url = 'http://sddevrepo.oceanobservatories.org/releases/',
    license = 'Apache 2.0',
    author = 'Andrew Bird',
    author_email = '',
    keywords = ['ooici','eoi'],
    packages = find_packages(),
    dependency_links = [
        'http://sddevrepo.oceanobservatories.org/releases/',
        'https://github.com/lukecampbell/python-gsw/tarball/master#egg=gsw-3.0.1a1',
    ],
    test_suite = '',
    install_requires = [
        'gsconfig',
    ],
    
)
