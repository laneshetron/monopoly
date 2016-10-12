from setuptools import setup

def readme():
    with open('README.md') as f:
        return f.read()

setup(name='monopoly',
      version='0.2.0',
      description='A karma bot for Hangouts and IRC.',
      long_description=readme(),
      url='https://github.com/laneshetron/monopoly.git',
      author='Lane Shetron',
      author_email='laneshetron@gmail.com',
      license='MIT',
      packages=['monopoly'],
      install_requires=['hangups', 'websocket-client', 'fuzzywuzzy', 'python-Levenshtein'],
      include_package_data=True,
      zip_safe=False)

# Include setup of custom hangups branch
