#!/usr/bin/env python
""" Setup file for Picopt
Reference:
https://hynek.me/articles/sharing-your-labor-of-love-pypi-quick-and-dirty/
"""
import sys
from setuptools import setup, find_packages
from pip.req import parse_requirements

__version__ = "1.3.0"
README_FILENAME = "README.rst"
REQUIREMENTS = {
    'prod': "requirements.txt",
    'dev': "requirements-dev.txt"
}


def parse_reqs(filename):
    """ parse setup requirements from a requirements.txt file """
    install_reqs = parse_requirements(filename, session=False)
    return [str(ir.req) for ir in install_reqs]

req_list = parse_reqs(REQUIREMENTS['prod'])
if len(sys.argv) > 2 and sys.argv[2] == ('develop'):
    req_list += parse_reqs(REQUIREMENTS['dev'])


with open(README_FILENAME, 'r') as readme_file:
    LONG_DESCRIPTION = readme_file.read()

setup(
    name='picopt',
    version=__version__,
    description='Optimize image files and comic archives with external tools',
    author='AJ Slater',
    author_email='aj@slater.net',
    url='https://github.com/ajslater/picopt/',
    py_modules=['picopt'],
    install_requires=req_list,
    entry_points={
        'console_scripts': [
            'picopt = picopt.cli:main'
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
        'Programming Language :: Python :: 3.4',
        'Topic :: Internet :: WWW/HTTP :: Site Management',
        'Topic :: Multimedia :: Graphics :: Graphics Conversion'
    ],
    packages=find_packages(),
    test_suite='picopt.tests',
)
