import unittest

from tox_in_docker import util


class TestGetDefaultImages(unittest.TestCase):
    BASES = [('py', 'python'), ('pypy', 'pypy')]

    def test_latest(self):

        for env, image_base in self.BASES:
            with self.subTest(env=env, image_base=image_base):
                res = util.get_default_image(env)
                self.assertEqual(res, f'{image_base}:latest')

    def test_major(self):
        for env, image_base in self.BASES:
            for version in range(1, 4):
                print(version, str(version))
                this_env = f'{env}{str(version)}'
                with self.subTest(env=env, this_env=this_env, image_base=image_base):
                    res = util.get_default_image(this_env)
                    print([res, image_base, version])
                    self.assertEqual(res, f'{image_base}:{version}')

    def test_minor(self):
        for env, image_base in self.BASES:
            for maj_version in [2, 3]:
                for min_version in [1, 2, 12]:
                    this_env = f'{env}{maj_version}{min_version}'
                    with self.subTest(env=env, this_env=this_env, min_version=min_version, maj_version=maj_version):
                        res = util.get_default_image(this_env)
                        self.assertEqual(res, f'{image_base}:{maj_version}.{min_version}')
        # I'm not sure if other pythons are effected, but at least py 3.10
        # environment can be `py10`
        with self.subTest(env=env, this_env='py10', min_version=10, maj_version=3):
            res = util.get_default_image('py10')
            self.assertEqual(res, f'{image_base}:3.10')

    def test_jython_raises_exception(self):
        for jython in ['jy', 'jython', 'jy27', 'jy2', 'jy3']:
            with self.assertRaises(util.NoJythonSupport):
                util.get_default_image(jython)
