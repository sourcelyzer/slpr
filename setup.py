from setuptools import setup, find_packages

setup(name='sllib',
      version='0.0.1',
      description='Sourcelyzer Plugin Repository',
      url='https://github.com/sourcelyzer/slpr',
      author='Alex Dow',
      author_email='adow@psikon.com',
      license='MIT',
      packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
      zip_safe=False
)
