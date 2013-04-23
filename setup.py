from distutils.core import setup
from ez_setup import use_setuptools
#from picopt import __version__ as version

use_setuptools()

with open('requirements.txt') as rfile:
        required = rfile.read().splitlines()

setup(name='picopt',
      version='0.9.0',
      description='Optimize image files with external tools',
      author='AJ Slater',
      author_email='aj@slater.net',
      url='http://github.com/ajslater/picopt/',
      py_modules=['picopt'],
      requires=required
      )
