project('eos-phone-home')

py = import('python').find_installation(pure: false)
test('run tests', py,
     args : ['-m', 'pytest', '-v'],
     workdir: meson.current_source_dir(),
    )

libdir = get_option('prefix') / 'lib'

install_data('50-eos-phone-home',
             install_dir : get_option('sysconfdir') / 'NetworkManager/dispatcher.d')
install_data('eos-phone-home', install_dir : libdir / 'eos-phone-home')

systemd_units = [
    'eos-phone-home.path',
    'eos-phone-home.service',
    'eos-phone-home.timer',
  ]

install_data(systemd_units, install_dir : libdir / 'systemd/system')
install_data('eos-phone-home.conf', install_dir : libdir / 'tmpfiles.d')
