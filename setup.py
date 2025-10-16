import sys

from setuptools import setup
# from setuptools.dist import Distribution


# class BinaryDistribution(Distribution):
#     """Distribution which always forces a binary package with platform name"""
#     def has_ext_modules(foo):
#         return sys.platform.startswith("win")

try:
    from wheel.bdist_wheel import bdist_wheel as _bdist_wheel

    class bdist_wheel(_bdist_wheel):
        def finalize_options(self):
            super().finalize_options()
            # Platform-specific wheel since we bundle native libraries
            self.root_is_pure = False

        def get_tag(self):
            python, abi, plat = _bdist_wheel.get_tag(self)
            # We don't contain any python source
            python, abi = "py2.py3", "none"
            return python, abi, plat
except ImportError:
    bdist_wheel = None


setup(
    # distclass=BinaryDistribution,
    cmdclass={"bdist_wheel": bdist_wheel},
)
