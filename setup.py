from distutils.core import setup
from ez_setup import use_setuptools
from pip.req import parse_requirements
from picopt import __version__

use_setuptools()

install_reqs=parse_requirements('requirements.txt')
req_list=[str(ir.req) for ir in install_reqs]

setup(
    name='picopt',
    version=__version__,
    description='Optimize image files and comic archives with external tools',
    author='AJ Slater',
    author_email='aj@slater.net',
    url='http://github.com/ajslater/picopt/',
    py_modules=['picopt'],
    install_requires=req_list,
    scripts=['picopt.py'],
    long_description=open('README.md').read(),
)
