Endless OS "Phone Home"
-----------------------

This is inspired by https://launchpad.net/canonical-poke imported from bzr to git
on Sat 9th July 2016. The "census" (simple sqlite stats processing) and
"sanitize" (log cleanup / anonymisation) were reinstated from the bzr
history and separate bzr branch for reference, but later removed.

We are using the anonymous counting approach as set out in
http://theravingrick.blogspot.co.uk/2010/08/can-we-count-users-without-uniquely.html
so that Endless can dermine the number of active systems without sending any
personally identifiable or trackable information.

As well as the daily "ping" message with an incrementing counter, we are
implementing a one-off "activate" request so we can tell how many systems have
been turned on. This request does include the machine serial number, but this
is only ever sent once per system, so cannot be used for any ongoing tracking.
