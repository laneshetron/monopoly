from setuptools import setup

def readme():
    with open('README.md') as f:
        return f.read()

setup(name='monopoly',
      version='0.1.1',
      description='A karma bot for Hangouts, Slack, and IRC.',
      long_description=readme(),
      url='https://github.com/laneshetron/monopoly.git',
      author='Lane Shetron',
      author_email='laneshetron@gmail.com',
      license='MIT',
      packages=['monopoly'],
      install_requires=['hangups==0.1.0-monopoly', 'websocket-client', 'fuzzywuzzy', 'python-Levenshtein'],
      dependency_links=['https://github.com/laneshetron/hangups/archive/v0.1.0-monopoly.zip#egg=hangups-0.1.0-monopoly'],
      include_package_data=True)
