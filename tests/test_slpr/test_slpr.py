import os
import random
import imp

TEST_FILE_DIR = os.path.realpath(os.path.dirname(__file__))
SLPR_MODULE   = os.path.realpath(os.path.join(TEST_FILE_DIR, '..', '..', 'slpr.py'))
REPO_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'test_repository')


def _load_module(modname, modfile):
    import imp
    return imp.load_source(modname, modfile)


def test_install_plugin():

    slpr = _load_module('slpr', SLPR_MODULE)

    repo_dir = os.path.join(REPO_DIR, str(random.randint(1,1000)))
    plugin_zip = os.path.join(os.path.dirname(__file__), 'fixtures', 'fake_plugin1', 'fake_plugin1.zip')

    slpr.install_plugin(plugin_zip, repo_dir)

    expected_plugin_location = os.path.join(repo_dir, 'testenv', 'fake_plugin1', '0.0.1', 'testenv.fake_plugin1-0.0.1.zip')
    expected_plugin_metadata = os.path.join(repo_dir, 'testenv', 'fake_plugin1', '0.0.1', 'metadata.json')

    print(expected_plugin_location)

    assert os.path.exists(expected_plugin_location)
    assert os.path.exists(expected_plugin_location + '.md5') == True
    assert os.path.exists(expected_plugin_location + '.sha256') == True
    assert os.path.exists(expected_plugin_metadata) == True


