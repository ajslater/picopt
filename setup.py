from distutils.core import setup
from ez_setup import use_setuptools
from version import __version__

use_setuptools()

with open('requirements.txt') as rfile:
        required = rfile.read().splitlines()

setup(
    name='picopt',
    version=__version__,
    description='Optimize image files and comic archives with external tools',
    author='AJ Slater',
    author_email='aj@slater.net',
    url='http://github.com/ajslater/picopt/',
    py_modules=['picopt'],
    requires=required,
    scripts=['picopt.py'],
    long_description=open('README.md').read(),
)
