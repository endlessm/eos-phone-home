# Endless OS "Phone Home"

This is inspired by https://launchpad.net/canonical-poke imported from bzr to git
on Sat 9th July 2016. The "census" (simple sqlite stats processing) and
"sanitize" (log cleanup / anonymisation) were reinstated from the bzr
history and separate bzr branch for reference, but later removed.

We are using the anonymous counting approach as set out in
http://theravingrick.blogspot.co.uk/2010/08/can-we-count-users-without-uniquely.html
so that Endless can determine the number of active systems without sending any
personally identifiable or trackable information.

As well as the daily "ping" message with an incrementing counter, we are
implementing a one-off "activate" request so we can tell how many systems have
been turned on.

## Configuration

`eos-phone-home` can be configured using the INI formatted file
`/etc/eos-phone-home.conf`. Options passed to `eos-phone-home` on the command
line take precedence over the configuration file.

The following settings are supported in the `global` section:

* `host` - The API server URL. (Default: `https://home.endlessm.com`)
* `debug` - Enable verbose output and disable any actual phoning home.
  (Default: `false`)
* `force` - Always collect data and enable verbose output. (Default: `false`)
* `exit_on_server_error` - Exit with a non-0 status if activation and/or ping
  can't be sent to the server. (Default: `false`)

For example:

```
[global]
host = https://home.example.com
exit_on_server_error = true
```
