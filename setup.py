# If true, then the svn revision won't be used to calculate the
# revision (set to True for real releases)
import os
RELEASE = False

# Make sure that `setuptools` is available
from distribute_setup import use_setuptools
use_setuptools()

# 
from setuptools import setup, find_packages

# Get description and __version__ without using import
readme = open("README.txt", "rt").read()
changes = open("CHANGES.txt", "rt").read()
long_description = readme + "\n\n" + changes
# TODO: `setup.py test` may fail, if description contains non-latin1 characters on windows
_test = long_description.encode("latin1")

g_dict = {}
exec(open("wplsync/_version.py").read(), g_dict)
__version__ = g_dict["__version__"]

# 'setup.py upload' fails on Vista, because .pypirc is searched on 'HOME' path
if not "HOME" in os.environ and  "HOMEPATH" in os.environ:
    os.environ.setdefault("HOME", os.environ.get("HOMEPATH", ""))
    print("Initializing HOME environment variable to '%s'" % os.environ["HOME"])


setup(name = "WplSync",
      version = __version__,
      author = "Martin Wendt",
      author_email = "wplsync@wwwendt.de",
      maintainer = "Martin Wendt",
      maintainer_email = "wplsync@wwwendt.de",
      url = "http://wplsync.googlecode.com/",
      description = "Python console script to synchronize media folders, using playlists as filter",
      long_description = readme + "\n\n" + changes,

        #Development Status :: 2 - Pre-Alpha
        #Development Status :: 3 - Alpha
        #Development Status :: 4 - Beta
        #Development Status :: 5 - Production/Stable

      classifiers = ["Development Status :: 2 - Pre-Alpha",
                     "Environment :: Console",
                     "Intended Audience :: End Users/Desktop",
                     "License :: OSI Approved :: MIT License",
                     "Natural Language :: English",
                     "Operating System :: OS Independent",
                     "Programming Language :: Python :: 2",
                     "Programming Language :: Python :: 3",
                     ],
      keywords = "playlist wpl folder sync", 
      license = "The MIT License",
#      install_requires = ["lxml"],
      # Add support for Mercurial revision control system, so we don't nee MANIFEST.in
      setup_requires = ["setuptools_hg"],
      packages = find_packages(exclude=[]),
#      py_modules = ["wplsync", "distribute_setup"],
      # Only works for data files that are under CVS/SVN control:
      package_data = {"": ["*.txt", "CHANGES.txt"],
                      "wplsync": ["*.txt", "CHANGES.txt"],},
      include_package_data=True,

      zip_safe = False,
#      extras_require = {},
#      tests_require = ["WebTest", ],
#      test_suite = "tests.test_all.run",
      entry_points = {
          "console_scripts" : ["wplsync = wplsync.wplsync:run"],
          },
      use_2to3 = True,
      )
