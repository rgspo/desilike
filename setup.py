import os
import sys
from setuptools import setup, find_packages


package_basename = 'desilike'
package_dir = os.path.join(os.path.dirname(__file__), package_basename)
sys.path.insert(0, package_dir)
import _version
version = _version.__version__


def get_yaml_files():
    for section in ['likelihoods', 'observables', 'theories']:
        for root, dirs, files in os.walk(os.path.join(package_dir, section)):
            for file in files:
                if file.endswith('.yaml'):
                    yield os.path.relpath(os.path.join(root, file), package_dir)


setup(name=package_basename,
      version=version,
      author='cosmodesi',
      author_email='',
      description='Package for DESI likelihoods',
      license='BSD3',
      url='http://github.com/cosmodesi/desilike',
      install_requires=['numpy', 'scipy', 'pyyaml', 'mpi4py', 'cosmoprimo @ git+https://github.com/cosmodesi/cosmoprimo', 'cython'],
      extras_require={'plotting': ['tabulate', 'getdist', 'anesthetic'], 'jax': ['jax[cpu]']},
      packages=find_packages(),
      package_data={package_basename: list(get_yaml_files())})
