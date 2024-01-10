from setuptools import setup, find_packages

# with open('requirements.txt') as fp:
#     install_requires = fp.read().split('\n')
#     install_requires = [ir for ir in install_requires if ir != '']

# print("Requirements:\n{}\n\n".format(install_requires))
PKG_NAME = "airbyte_client"
packages = [PKG_NAME] + [PKG_NAME + '.' + pkg for pkg in find_packages(PKG_NAME)]
print(packages)

setup(name=PKG_NAME,
      version='0.0.1',
      description='Python library that implements Airbyte protocol',
      author='Mikhail Masyagin',
      author_email='mikhail.masyagin@anec.app',
      # install_requires=install_requires,
      dependency_links=[],
      packages=packages,
      include_package_data=True)
