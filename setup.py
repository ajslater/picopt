from distutils.core import setup
from ez_setup import use_setuptools
from picopt import __revision__ as version

use_setuptools()

setup(name='picopt',
      version=version,
      description='Optimize image files with external tools',
      author='AJ Slater',
      author_email='aj@slater.net',
      url='http://www.python.org/sigs/',
      py_modules=['picopt'],
      requires=['Image', 'ImageFile']
      )
