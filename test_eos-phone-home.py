import imp
import os

import pytest

SRCDIR = os.path.dirname(__file__)
eos_phone_home_path = os.path.join(SRCDIR, 'eos-phone-home')
eos_phone_home = imp.load_source("m", eos_phone_home_path)


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

    endless_serial_number_file = tmpdir.join('sys', 'class',
                                             'endless_mfgdata', 'entries',
                                             'SSN')
    endless_serial_number_file.write('  serial  ', ensure=True)

    product_info = app._get_product_info()
    expected = eos_phone_home.ProductInfo('vendor1', 'model1', 'serial')
    assert product_info == expected


def test_get_product_info_arm_missing_serial(tmpdir, app):
    device_tree_product_info_file = tmpdir.join('proc', 'device-tree',
                                                'compatible')
    device_tree_product_info_file.write_binary(b'vendor1,model1\0'
                                               b'vendor2,model2\0',
                                               ensure=True)

    product_info = app._get_product_info()
    expected = eos_phone_home.ProductInfo('vendor1', 'model1', None)
    assert product_info == expected


def test_get_product_info_arm_missing_dt(tmpdir, app):
    endless_serial_number_file = tmpdir.join('sys', 'class',
                                             'endless_mfgdata', 'entries',
                                             'SSN')
    endless_serial_number_file.write('  serial  ', ensure=True)

    product_info = app._get_product_info()
    expected = eos_phone_home.ProductInfo(None, None, 'serial')
    assert product_info == expected


def test_get_product_info_x86(tmpdir, app):
    dmi_dir = tmpdir.join('sys', 'class', 'dmi', 'id')
    dmi_dir.join('sys_vendor').write('  vendor', ensure=True)
    dmi_dir.join('product_name').write(' product')
    dmi_dir.join('product_serial').write('serial  ')

    product_info = app._get_product_info()
    expected = eos_phone_home.ProductInfo('vendor', 'product', 'serial')
    assert product_info == expected


def test_get_product_info_x86_missing_vendor(tmpdir, app):
    dmi_dir = tmpdir.join('sys', 'class', 'dmi', 'id')
    dmi_dir.join('product_name').write(' product', ensure=True)
    dmi_dir.join('product_serial').write('serial  ')

    product_info = app._get_product_info()
    expected = eos_phone_home.ProductInfo(None, 'product', 'serial')
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
        'serial': 'unknown',
        # mac_hash, however, is omitted if it can't be determined.
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
