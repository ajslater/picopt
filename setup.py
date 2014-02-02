""" Setup file for Picopt
Reference:
https://hynek.me/articles/sharing-your-labor-of-love-pypi-quick-and-dirty/
"""
from distutils.core import setup
from pip.req import parse_requirements
from picopt import __version__

INSTALL_REQS = parse_requirements('requirements.txt')
REQ_LIST = [str(ir.req) for ir in INSTALL_REQS]

setup(
    name='picopt',
    version=__version__,
    description='Optimize image files and comic archives with external tools',
    author='AJ Slater',
    author_email='aj@slater.net',
    url='https://github.com/ajslater/picopt/',
    py_modules=['picopt'],
    install_requires=REQ_LIST,
    scripts=['picopt.py'],
    long_description=open('README.md').read(),
    license="GPL v2",
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Environment :: Console',
        'License :: OSI Approved :: GPL v2',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Topic :: Internet :: WWW/HTTP :: Site Management',
        'Topic :: Multimedia :: Graphics :: Graphics Conversion'
    ]
)
