#!/usr/bin/env python
"""Setup file for Picopt.

Reference:
https://hynek.me/articles/sharing-your-labor-of-love-pypi-quick-and-dirty/
"""
from __future__ import absolute_import, division, print_function

import os
import re
import sys

from pip.req import parse_requirements
from setuptools import find_packages, setup

README_FILENAME = "README.rst"
REQUIREMENTS = {
    'prod': "requirements.txt",
    'dev': "requirements-dev.txt"
}


def get_version(package):
    """Return package version as listed in `__version__` in `init.py`."""
    with open(os.path.join(package, '__init__.py'), 'rb') as init_py:
        src = init_py.read().decode('utf-8')
        return re.search("__version__ = ['\"]([^'\"]+)['\"]", src).group(1)


def parse_reqs(filename):
    """Parse setup requirements from a requirements.txt file."""
    install_reqs = parse_requirements(filename, session=False)
    return [str(ir.req) for ir in install_reqs]


def get_req_list():
    """Get the requirements by weather we're building develop or not."""
    req_list = parse_reqs(REQUIREMENTS['prod'])
    if len(sys.argv) > 2 and sys.argv[2] == ('develop'):
        req_list += parse_reqs(REQUIREMENTS['dev'])
    return req_list


with open(README_FILENAME, 'r') as readme_file:
    LONG_DESCRIPTION = readme_file.read()

setup(
    name='picopt',
    version=get_version('picopt'),
    description='Optimize image files and comic archives with external tools',
    author='AJ Slater',
    author_email='aj@slater.net',
    url='https://github.com/ajslater/picopt/',
    install_requires=get_req_list(),
    entry_points={
        'console_scripts': [
            'picopt=picopt.cli:main'
        ]
    },
    long_description=LONG_DESCRIPTION,
    license="GPLv2",
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: System Administrators',
        'Natural Language :: English',
        'Environment :: Console',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP :: Site Management',
        'Topic :: Multimedia :: Graphics :: Graphics Conversion'
    ],
    packages=find_packages(),
    test_suite='tests',
)
