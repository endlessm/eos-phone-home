from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import json
import os
import sys
from textwrap import dedent

import pytest

SRCDIR = os.path.dirname(__file__)
eos_phone_home_path = os.path.join(SRCDIR, 'eos-phone-home')
eos_phone_home_loader = SourceFileLoader('eos_phone_home', eos_phone_home_path)
eos_phone_home_spec = spec_from_loader('eos_phone_home', eos_phone_home_loader)
eos_phone_home = module_from_spec(eos_phone_home_spec)
sys.modules['eos_phone_home'] = eos_phone_home
eos_phone_home_spec.loader.exec_module(eos_phone_home)


@pytest.fixture
def app(tmpdir):
    return eos_phone_home.PhoneHome(True, False, root=tmpdir.strpath)


def test_instantiate(tmpdir, app):
    assert tmpdir.strpath == app._root


def test_get_product_info_arm(tmpdir, app):
    device_tree_product_info_file = tmpdir.join('proc', 'device-tree',
                                                'compatible')
    device_tree_product_info_file.write_binary(b'vendor1,model1\0'
                                               b'vendor2,model2\0',
                                               ensure=True)

    product_info = app._get_product_info()
    expected = eos_phone_home.ProductInfo('vendor1', 'model1')
    assert product_info == expected


def test_get_product_info_arm_missing_dt(tmpdir, app):
    product_info = app._get_product_info()
    expected = eos_phone_home.ProductInfo(None, None)
    assert product_info == expected


def test_get_product_info_x86(tmpdir, app):
    dmi_dir = tmpdir.join('sys', 'class', 'dmi', 'id')
    dmi_dir.join('sys_vendor').write('  vendor', ensure=True)
    dmi_dir.join('product_name').write(' product')

    product_info = app._get_product_info()
    expected = eos_phone_home.ProductInfo('vendor', 'product')
    assert product_info == expected


def test_get_product_info_x86_missing_vendor(tmpdir, app):
    dmi_dir = tmpdir.join('sys', 'class', 'dmi', 'id')
    dmi_dir.join('product_name').write(' product', ensure=True)

    product_info = app._get_product_info()
    expected = eos_phone_home.ProductInfo(None, 'product')
    assert product_info == expected


def test_standalone_system_is_detected(tmpdir, app):
    cmdline = ''
    tmpdir.join('proc', 'cmdline').write(cmdline, ensure=True)

    assert app._get_dualboot() is False
    assert app._get_live() is False


def test_dualboot_system_is_detected(tmpdir, app):
    cmdline = '''
    endless.image.device=UUID=blahblah
    endless.image.path=/endless/endless.img
    '''.strip()
    tmpdir.join('proc', 'cmdline').write(cmdline, ensure=True)

    assert app._get_dualboot() is True
    assert app._get_live() is False


def test_live_system_is_detected(tmpdir, app):
    cmdline = '''
    endless.image.device=UUID=blahblah
    endless.image.path=/endless/endless.img
    endless.live_boot
    '''.strip()
    tmpdir.join('proc', 'cmdline').write(cmdline, ensure=True)

    assert app._get_dualboot() is False
    assert app._get_live() is True


def test_count_initial(tmpdir, app):
    assert app._get_count() == 0


def test_count_subsequent(tmpdir, app):
    tmpdir.join('var', 'lib', 'eos-phone-home', 'count').write('5',
                                                               ensure=True)
    assert app._get_count() == 5


def test_build_activation_request_when_fields_cannot_be_determined(tmpdir,
                                                                   app):
    tmpdir.join('proc', 'cmdline').write('', ensure=True)

    request = app.build_request(app.ACTIVATION_VARIABLES)
    assert request == {
        'dualboot': False,
        'live': False,
        # These variables are set to 'unknown' rather than omitted for
        # backwards-compatibility.
        'image': 'unknown',
        'release': 'unknown',
        'vendor': 'unknown',
        'product': 'unknown',
    }


def test_build_ping_request_initial(tmpdir, app):
    '''https://phabricator.endlessm.com/T20993'''
    tmpdir.join('proc', 'cmdline').write('', ensure=True)

    request = app.build_request(app.PING_VARIABLES)
    assert request == {
        'dualboot': False,
        'image': 'unknown',
        'release': 'unknown',
        'vendor': 'unknown',
        'product': 'unknown',
        'metrics_enabled': False,
        'metrics_environment': 'unknown',
        'count': 0,
    }


def test_build_ping_request_subsequent(tmpdir, app):
    tmpdir.join('proc', 'cmdline').write('', ensure=True)
    tmpdir.join('var', 'lib', 'eos-phone-home', 'count').write('5',
                                                               ensure=True)

    request = app.build_request(app.PING_VARIABLES)
    assert request == {
        'dualboot': False,
        'image': 'unknown',
        'release': 'unknown',
        'vendor': 'unknown',
        'product': 'unknown',
        'metrics_enabled': False,
        'metrics_environment': 'unknown',
        'count': 5,
    }


def test_cli_options(tmpdir, monkeypatch):
    """Test eos-phone-home CLI options"""
    config_path = tmpdir.join('eos-phone-home.conf')
    attrs_path = tmpdir.join('attributes.json')

    def read_attributes():
        with open(attrs_path, 'r') as f:
            return json.load(f)

    def write_attributes(attrs):
        with open(attrs_path, 'w') as f:
            return json.dump(attrs, f)

    def mock_argv(*args):
        monkeypatch.setattr(
            sys,
            'argv',
            ['eos-phone-home', f'--config={config_path}'] + list(args),
        )

    def mock_run(self, exit_on_server_error):
        write_attributes({
            'debug': self._debug,
            'force': self._force,
            'api_host': self._api_host,
            'exit_on_server_error': exit_on_server_error,
        })

    monkeypatch.setattr(eos_phone_home.PhoneHome, 'run', mock_run)

    mock_argv()
    eos_phone_home.main()
    attrs = read_attributes()
    assert attrs == {
        'debug': False,
        'force': False,
        'api_host': eos_phone_home.PhoneHome.DEFAULT_API_HOST,
        'exit_on_server_error': False,
    }

    mock_argv('--debug')
    eos_phone_home.main()
    attrs = read_attributes()
    assert attrs == {
        'debug': True,
        'force': False,
        'api_host': eos_phone_home.PhoneHome.DEFAULT_API_HOST,
        'exit_on_server_error': False,
    }

    mock_argv('--force')
    eos_phone_home.main()
    attrs = read_attributes()
    assert attrs == {
        'debug': True,
        'force': True,
        'api_host': eos_phone_home.PhoneHome.DEFAULT_API_HOST,
        'exit_on_server_error': False,
    }

    mock_argv('--host=https://home.example.com')
    eos_phone_home.main()
    attrs = read_attributes()
    assert attrs == {
        'debug': False,
        'force': False,
        'api_host': 'https://home.example.com',
        'exit_on_server_error': False,
    }

    mock_argv('-t', 'https://home.example.com')
    eos_phone_home.main()
    attrs = read_attributes()
    assert attrs == {
        'debug': False,
        'force': False,
        'api_host': 'https://home.example.com',
        'exit_on_server_error': False,
    }

    mock_argv('--exit-on-server-error')
    eos_phone_home.main()
    attrs = read_attributes()
    assert attrs == {
        'debug': False,
        'force': False,
        'api_host': eos_phone_home.PhoneHome.DEFAULT_API_HOST,
        'exit_on_server_error': True,
    }

    # Test interactions between config file and CLI options
    with open(config_path, 'w') as f:
        f.write(dedent(
            """\
            [global]
            host = https://home.example.com
            debug = true
            """
        ))
    mock_argv()
    eos_phone_home.main()
    attrs = read_attributes()
    assert attrs == {
        'debug': True,
        'force': False,
        'api_host': 'https://home.example.com',
        'exit_on_server_error': False,
    }

    with open(config_path, 'w') as f:
        f.write(dedent(
            """\
            [global]
            host = https://home.example.com
            debug = false
            force = false
            """
        ))
    mock_argv('--force', '--host=https://foo.example.com')
    eos_phone_home.main()
    attrs = read_attributes()
    assert attrs == {
        'debug': True,
        'force': True,
        'api_host': 'https://foo.example.com',
        'exit_on_server_error': False,
    }


def test_config(tmpdir):
    """Test Config class"""
    config_path = tmpdir.join('eos-phone-home.conf')

    # Default Config instance
    config = eos_phone_home.Config()
    assert config == eos_phone_home.Config(
        host=eos_phone_home.PhoneHome.DEFAULT_API_HOST,
        debug=False,
        force=False,
        exit_on_server_error=False,
    )

    # No config file
    config = eos_phone_home.Config.from_path(config_path)
    assert config == eos_phone_home.Config(
        host=eos_phone_home.PhoneHome.DEFAULT_API_HOST,
        debug=False,
        force=False,
        exit_on_server_error=False,
    )

    # Empty config file
    with open(config_path, 'w'):
        pass
    config = eos_phone_home.Config.from_path(config_path)
    assert config == eos_phone_home.Config(
        host=eos_phone_home.PhoneHome.DEFAULT_API_HOST,
        debug=False,
        force=False,
        exit_on_server_error=False,
    )

    # Full config file
    with open(config_path, 'w') as f:
        f.write(dedent(
            """\
            [global]
            host = https://home.example.com
            debug = true
            force = yes
            exit_on_server_error = 1
            """
        ))
    config = eos_phone_home.Config.from_path(config_path)
    assert config == eos_phone_home.Config(
        host='https://home.example.com',
        debug=True,
        force=True,
        exit_on_server_error=True,
    )

    # Config file and overrides
    with open(config_path, 'w') as f:
        f.write(dedent(
            """\
            [global]
            host = https://home.example.com
            exit_on_server_error = true
            """
        ))
    overrides = {'host': 'https://foo.example.com', 'force': True}
    config = eos_phone_home.Config.from_path(config_path, overrides)
    assert config == eos_phone_home.Config(
        host='https://foo.example.com',
        debug=False,
        force=True,
        exit_on_server_error=True,
    )
