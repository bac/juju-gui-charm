"""Juju GUI deploy module tests."""

import os
import shutil
import tempfile
import unittest

import mock

from deploy import (
    juju_deploy,
    setup_repository,
)


class TestSetupRepository(unittest.TestCase):

    def setUp(self):
        # Create a directory structure for the charm source.
        self.source = tempfile.mkdtemp()
        self.charm_name = os.path.basename(self.source)
        self.addCleanup(shutil.rmtree, self.source)
        # Create a file in the source dir.
        _, self.root_file = tempfile.mkstemp(dir=self.source)
        # Create a Bazaar repository directory with a file in it.
        bzr_dir = os.path.join(self.source, '.bzr')
        os.mkdir(bzr_dir)
        tempfile.mkstemp(dir=bzr_dir)
        # Create a tests directory including a .venv directory and a file.
        self.tests_dir = os.path.join(self.source, 'tests')
        venv_dir = os.path.join(self.tests_dir, '.venv')
        os.makedirs(venv_dir)
        tempfile.mkstemp(dir=venv_dir)
        # Create a test file.
        _, self.tests_file = tempfile.mkstemp(dir=self.tests_dir)

    def assert_dir_exists(self, path):
        self.assertTrue(
            os.path.isdir(path),
            'the directory {!r} does not exist'.format(path))

    def assert_files_equal(self, expected, path):
        fileset = set()
        for dirpath, _, filenames in os.walk(path):
            relpath = os.path.relpath(dirpath, path)
            if relpath == '.':
                relpath = ''
            else:
                fileset.add(relpath + os.path.sep)
            fileset.update(os.path.join(relpath, name) for name in filenames)
        self.assertEqual(expected, fileset)

    def check_repository(self, repo, series):
        self.assertEqual(tempfile.tempdir, os.path.split(repo)[0])
        self.assert_dir_exists(repo)
        self.assertEqual([series], os.listdir(repo))
        series_dir = os.path.join(repo, series)
        self.assert_dir_exists(series_dir)
        self.assertEqual([self.charm_name], os.listdir(series_dir))
        self.assert_dir_exists(os.path.join(series_dir, self.charm_name))

    def test_repository(self):
        # The charm repository is correctly created with the default series.
        repo = setup_repository(self.source)
        self.check_repository(repo, 'precise')

    def test_series(self):
        # The charm repository is created with the given series.
        repo = setup_repository(self.source, series='raring')
        self.check_repository(repo, 'raring')

    def test_charm_files(self):
        # The charm files are correctly copied inside the repository.
        repo = setup_repository(self.source)
        charm_dir = os.path.join(repo, 'precise', self.charm_name)
        test_dir_name = os.path.basename(self.tests_dir)
        expected = set([
            os.path.basename(self.root_file),
            test_dir_name + os.path.sep,
            os.path.join(test_dir_name, os.path.basename(self.tests_file))
        ])
        self.assert_files_equal(expected, charm_dir)


class TestJujuDeploy(unittest.TestCase):

    unit_info = {'public-address': 'unit.example.com'}
    charm = 'test-charm'
    expose_call = mock.call('expose', charm)
    local_charm = 'local:{}'.format(charm)
    repo = '/tmp/repo/'

    @mock.patch('deploy.juju')
    @mock.patch('deploy.wait_for_unit')
    @mock.patch('deploy.setup_repository')
    def call_deploy(
            self, mock_setup_repository, mock_wait_for_unit, mock_juju,
            **kwargs):
        mock_setup_repository.return_value = self.repo
        mock_wait_for_unit.return_value = self.unit_info
        charm_source = kwargs.setdefault(
            'charm_source', os.path.join(os.path.dirname(__file__), '..'))
        unit_info = juju_deploy(self.charm, **kwargs)
        mock_setup_repository.assert_called_once_with(charm_source)
        # The unit address is correctly returned.
        self.assertEqual(self.unit_info, unit_info)
        self.assertEqual(1, mock_wait_for_unit.call_count)
        # Juju is called two times: deploy and expose.
        juju_calls = mock_juju.call_args_list
        self.assertEqual(2, len(juju_calls))
        deploy_call, expose_call = juju_calls
        self.assertEqual(self.expose_call, expose_call)
        return deploy_call

    def test_deployment(self):
        # The function deploys and exposes the given charm.
        expected_deploy_call = mock.call(
            'deploy',
            '--repository', self.repo,
            self.local_charm,
        )
        deploy_call = self.call_deploy()
        self.assertEqual(expected_deploy_call, deploy_call)

    def test_options(self):
        # The function handles charm options.
        mock_config_file = mock.Mock()
        mock_config_file.name = '/tmp/config.yaml'
        expected_deploy_call = mock.call(
            'deploy',
            '--repository', self.repo,
            '--config', mock_config_file.name,
            self.local_charm,
        )
        with mock.patch('deploy.make_charm_config_file') as mock_callable:
            mock_callable.return_value = mock_config_file
            deploy_call = self.call_deploy(options={'foo': 'bar'})
        self.assertEqual(expected_deploy_call, deploy_call)

    def test_force_machine(self):
        # The function can deploy charms in a specified machine.
        expected_deploy_call = mock.call(
            'deploy',
            '--repository', self.repo,
            '--force-machine', '42',
            self.local_charm,
        )
        deploy_call = self.call_deploy(force_machine=42)
        self.assertEqual(expected_deploy_call, deploy_call)

    def test_charm_source(self):
        # The function can deploy a charm from a specific source.
        expected_deploy_call = mock.call(
            'deploy',
            '--repository', self.repo,
            self.local_charm,
        )
        deploy_call = self.call_deploy(charm_source='/tmp/source/')
        self.assertEqual(expected_deploy_call, deploy_call)
