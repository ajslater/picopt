from distutils.core import setup
from ez_setup import use_setuptools

use_setuptools()

setup(name='picopt',
      version='0.7.0',
      description='Optimize image files with external tools',
      author='AJ Slater',
      author_email='aj@slater.net',
      url='http://www.python.org/sigs/',
      py_modules=['picopt'],
      requires=['Image', 'ImageFile']
      )
