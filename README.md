# Pioneer

Your Swiss army knife for NETCONF, YANG and NSO NEDs.

# Purpose

Pioneer is a collection of tools that make the life in NSO easier when
working in with NETCONF/YANG devices.

* The NETCONF tools allow the NSO operator to issue simple NETCONF
hello, get and get-config requests to the device to check basic
NETCONF support.

* The YANG tools allow the operator to build a NETCONF NED for the
device, potentially disabling YANG models that are fail to compile or
operate correctly, or simply are out of scope.

* The config tools allow working with device configuration using
files, which is useful when debuggin situations when the device
configuration violates the device's YANG contract, and when testing
transactionality properties.

* The log tools allow reviewing the raw NETCONF communication between
NSO and the device.

See usage examples below.

# Documentation

Apart from this file, the main documentation is the pioneer.yang file,
where each command is described.

# Dependencies

In order to run all of the functionality, you will need to have (in
the path) the following components. If something is missing, your most
important use cases may still work, but some tools will not.

* NSO 4.1+
* Python 2.7+ or 3+
* Paramiko (SSH library for Python)
* xsltproc
* bash
* pyang from NSO

You can paste this command into a terminal to quickly check that all
dependencies are fulfilled:

    which ncs && which python && python -c "import paramiko" \
    && which xsltproc && which bash && which pyang && echo "All Fine"

# Build instructions

Normal NSO package build:

    make -C packages/pioneer/src/ clean all

# Testing

Lux test cases in the test/ directory. Run as

    cd packages/pioneer/test/
    lux internal

# Usage examples

## NETCONF tools

When you encounter a new NETCONF device for the first time, the first
thing you need to do is to add it to the NSO device list under 
devices device.

Create an authgroup with login credentials for the device. Currently,
Pioneer will only work with default-map, not umap.

    devices authgroups group my-group
     default-map remote-name my-user-name
     default-map remote-password my-password

Create a device list entry for the device:

    devices device my-netconf-device
     address         10.1.1.1
     port            8300
     authgroup       my-group
     device-type netconf
     trace           raw
     state admin-state unlocked

Default port for NETCONF is 830. No need to specify port if the device
is using that port. Trace may set to false, Pioneer does not depend on
tracing being enabled.

Fetch the SSH host key from the device:

    devices device my-netconf-device ssh fetch-host-keys

And commit all of this:

    commit

At this point, it should be possible to connect

    connect

Any attempt to sync-from will of course fail since we don't yet have a
NETCONF NED for the device.

### pioneer netconf hello

What we can do is to have a look at the hello message.

    devices device my-netconf-device pioneer netconf hello

Which should give you a response along these lines:

    <hello xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
     <capabilities>
      <capability>urn:ietf:params:netconf:base:1.1</capability>
    ...
     </capabilities>
     <session-id>2878199957</session-id>
    </hello>

If connection fails, check your device list settings above and try
again. If you want to remove NSO and Pioneer from the mix, you should
get the above response from a Linux prompt if you ussue:

    ssh user@address -p port -s netconf

### pioneer netconf get, get-config

If hello repsonds correctly, you may want to try a simple get and
get-config before proceeding to build a NETCONF NED. Here are the
commands:

    devices device my-netconf-device pioneer netconf get
    devices device my-netconf-device pioneer netconf get-config

## YANG tools

Let's build a NETCONF NED for the device.

### pioneer yang fetch-list, download

First we need to get our hands on the YANG models describing the
NETCONF interface for the device. The best way is to download them
directly from the device. This way we ensure we have the right version
for the device.

    devices device my-netconf-device pioneer yang fetch-list
    devices device test1a pioneer yang download

This should give us a list of YANG files supported by the
device. Pioneer tries to get this list in three different ways, the
hello message (incomplete list, but better than nothing),
netconf-monitoring get-schema operation using xpath and subtree
filtering.  The second command will attempt to download them from the
device. If this doesn't work, then you need to contact the supplier of
the device and ask for the appropriate YANG modules (of the correct
version).

### pioneer yang build-netconf-ned

After the files have been downloaded they must built before they can
be used. For NSO versions prior to 4.2 all NSO built-in YANG models
needs to be disabled, see “Circular dependency for module
‘tailf-ncs’” below for details.

    devices device my-netconf-device pioneer yang build-netconf-ned
    …
    Build complete. Run install-netconf-ned, then run 'packages reload' to use the package
    ned-directory /tmp/packages/my-netconf-device

### pioneer yang disable, enable

If not all YANG models are required or if any contain errors they can
be disabled using pioneer yang disable. The following example shows
how to disable the module broken from the build:

    devices device my-netconf-device pioneer yang disable name-pattern broken
    Disabling module broken

You can use wild-cards "broken*" or list multiple names inside double
quotes separated with space "broken-module-1 broken-module-2".

If you would like to re-enable a module that you have disabled, you
can use the enable command in a similar way.

    devices device my-netconf-device pioneer yang enable name-pattern broken

### pioneer yang show-list, delete

Use show-list to show which YANG modules are currently available, and
which state they are in (enabled, disabled).

    devices device my-netconf-device pioneer yang show-list

You may also delete YANG files that you don't want at all, i.e. in
order to download it again.

    devices device my-netconf-device pioneer yang delete name-pattern broken

### pioneer yang check-dependencies

YANG modules often refer to one another (using import and include). A
YANG module that refers to another module which has been disabled,
deleted or never downloaded will not compile, and will have to be
disabled. To find out about dependencies between YANG modules, run
check-dependencies.

    devices device my-netconf-device pioneer yang check-dependencies

When you have a consistent set of enabled YANG files, you can try
building it again using the build-netconf-ned command.

### pioneer yang install-netconf-ned, uninstall-netconf-ned

Once the netconf-ned is built, you need to install it into the running
NSO runtime directory. Use the install-netconf-ned to do that.

    devices device my-netconf-device pioneer yang install-netconf-ned

In order to make NSO use the new package, you also need to run a
packages reload.

    packages reload

If you don't want the netconf-ned in your packages directory any more,
you can uninstall it. To actually unload it from NSO, you need to run
packages reload again.

    devices device my-netconf-device pioneer yang uninstall-netconf-ned
    packages reload

## Config tools

As the NETCONF NED is up and running, it's time to start using the
device from NSO.

Let's go into configuration mode

    config

The first thing to do is a sync-from. With the new NETCONF NED loaded,
this should now work.

    devices device my-netconf-device sync-from

### pioneer config sync-from-into-file

If the sync-from doesn't work, there may be a number of different
reasons. One of the most common ones is that the device has
configuration data on board that violates the YANG specification of
valid data. NSO will not load data from such liars!

In order to find out what data this may be, the sync-from-into-file
command is useful. It gets the (potentially invalid) configuration
from the device and stores it into a local file. You can then proceed
to load and edit this file until the violation(s) are removed. This
exercise will give you a good idea about how to change the device
configuration so that it conforms to the YANG, and what error to
report to the device vendor.

If you would like to inspect the contents of a file from the NSO
configuration mode, you can do that using the command

    do file show my-filename

There is no built-in way to edit files, however.

When NSO loads from a file, it employs "strict loading", which means
that any unexpected elements will be rejected. When NSO runs a
sync-from, it employs "lax loading", which accepts+ignores any
unexpected elements in the data.

Because of this, it is often useful to sync-from-into-file and then
load the file, just to ensure NSO doesn't silently drop any data
coming from the device.

    devices device my-netconf-device pioneer config \
     sync-from-into-file filename my-device-config.xml
    load merge my-device-config.xml

A variant of this command saves the configuration as a device template
instead, which you can edit and reuse later.

    devices device my-netconf-device pioneer config \
     sync-from-into-file as-template my-template \
     filename my-device-template.xml
    load merge my-device-template.xml
    devices device my-netconf-device apply-template \
     template-name my-template

### pioneer config import-into-file

Sometimes we get XML config files for a device that we would like to
load into NSO. This does not work straight off, since in NSO the
device configuration sits under "devices device config" of a
particular device. The import-into-file command can take such a device
XML file and generate a new file that loads nicely into NSO.

## Config tools for testing device transactionality

Apart from testing some basic NETCONF operations and building NETCONF
NEDs, Pioneer can also be used to test that a device support the
proper transactional behavior. Among other things, transactional
behavior means that a device can accept any valid configuration
regardless of the state it is in currently. For all transactions it
must also be true that the device configuration becomes exactly the
previous configuration modified by the transaction. In other words,
it's not acceptable that a device modifies any other parts of the
configuration than the ones touched by the transaction.

Pioneer can test the conformance with these rules automatically, but
requires a smart selection of input configurations in order to find
something useful. This is how it is done.

### pioneer config record-state, list-states, delete-state

Configure the device to an interesting configuration state, and make
sure NSO is in sync with the device. Changes may be entered directly
on the device, followed by a sync-from in NSO. Or changes may be
entered in NSO and committed to the device. Once a configuration is
running fine on the device and NSO is in sync, issue the operational
command:

    devices device <device-name> pioneer config record-state state-name <state-name>

The state name needs to be a valid file name, but can otherwise be
chosen freely. The name will be used later to describe which
configuration state transitions that have issues.

Keep doing this with interesting configurations for a while, so that
you have at least 4 states recorded, up to maybe a few dozens. You can
list the names of the states you have recorded, or delete ones you
don't want to keep using:

    devices device <device-name> pioneer config list-states
    devices device <device-name> pioneer config delete-state state-name <state-name>

### pioneer config explore-transitions

Then, when enough states have been collected, Pioneer can start
testing that all transitions work flawlessly. By default all
transitions are tried. That should give a safe result. Since testing
all-to-all configuration transitions grows exponentially with the
number of states, it's also possible to limit the number of
transitions to try out. The test will then not be conclusive, but
maybe more reasonable to run. You can run start the test in any of
these ways:

    devices device <device-name> pioneer config explore-transitions
    devices device <device-name> pioneer config explore-transitions stop-after { seconds 30 }
    devices device <device-name> pioneer config explore-transitions stop-after { minutes 5 }
    devices device <device-name> pioneer config explore-transitions stop-after { hours 12 }
    devices device <device-name> pioneer config explore-transitions stop-after { days 2 }
    devices device <device-name> pioneer config explore-transitions stop-after { cases 20 }
    devices device <device-name> pioneer config explore-transitions stop-after { percent 10 }

The sequence of transitions to try is selected randomly. Two different runs will therefore not yield the same test pattern.

A test run might look like this:

    admin@ncs# devices device xr pioneer config explore-transitions stop-after { percent 10 }
    Found 8 states recorded for device xr which gives a total of 56 transitions.

    Starting from known state noloop8
    ... failed setting known state

    Starting from known state bundle-vrf
    Transition 1/56: bundle-vrf ==> bundle-vrf-ipv4
    Transition 2/56: bundle-vrf-ipv4 ==> bundle-vrf-ipv46
    Transition 3/56: bundle-vrf-ipv46 ==> bundle-vrf-ipv4
    Transition 4/56: bundle-vrf-ipv4 ==> bundle-vrf
    Transition 5/56: bundle-vrf ==> bundle-vrf-ipv46
    Transition 6/56: bundle-vrf-ipv46 ==> bundle-vrf
    Requested stop-after time limit reached
    success Completed successfully

The comment "...failed setting known state" is an indication that
something isn't right. But since Pioneer didn't know exactly what
state the device was in before we started (or after a transaction has
failed) it's hard to give instructions on how to repeat the issue, so
this problem is ignored.

If an issue is found, the outcome might look like this:

    admin@ncs# devices device xr pioneer config explore-transitions stop-after { percent 10 }
    Found 8 states recorded for device xr which gives a total of 56 transitions.

    Starting from known state bundle-vrf-ipv4
    Transition 1/56: bundle-vrf-ipv4 ==> bundle-vrf-ipv46
    Transition 2/56: bundle-vrf-ipv46 ==> bundle-vrf-ipv4
    Transition 3/56: bundle-vrf-ipv4 ==> bundle-vrf
    Transition 4/56: bundle-vrf ==> bundle-vrf-ipv4
    Transition 5/56: bundle-vrf-ipv4 ==> initial
       transaction-failed

    Starting from known state no-bundle-ipv46
    Transition 6/56: no-bundle-ipv46 ==> bundle-vrf-ipv4
    Requested stop-after coverage limit reached
    failure transaction-failed: bundle-vrf-ipv4 ==> initial

Here, the transition from state bundle-vrf-ipv4 to initial
failed. 'transaction-failed' means the device refused to go between
these two states. If you'd see 'out-of-sync', that means the
transaction was accepted by the device, but the configuration of the
device is different than expected. Usually this means the device
created/changed some other values than the ones specified in the
transaction. In any case, the device configuration isn't what it
should be. Assuming netconf tracing was enabled, this failure can now
be debugged by manually invoking the configuration states in question:

    devices device <device-name> pioneer config transition-to-state state-name <state-name>
    admin@ncs# devices device xr pioneer config transition-to-state state-name bundle-vrf-ipv4
    success Done
    admin@ncs# devices device xr pioneer config transition-to-state state-name initial        
    failure transaction-failed
    admin@ncs# file show logs/netconf-xr.trace 
    ...
    <rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
         message-id="4">
      <edit-config xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
        <target>
          <candidate/>
        </target>
        <test-option>test-then-set</test-option>
        <error-option>rollback-on-error</error-option>
        <config>
          <interface-configurations xmlns="http://cisco.com/ns/yang/Cisco-IOS-XR-ifmgr-cfg">
            <interface-configuration>
    ...
        <error-message xml:lang="en">'RSI' detected the 'fatal' condition 'The interface's numbered and unnumbered IPv4/IPv6 addresses must be removed prior to changing or deleting the VRF'</error-message>
      </rpc-error>
    </rpc-reply>

Clearly, a violation of the transactional behavior. The device may
also have log files worth looking at to understand the
issue.

# Troubleshooting

### Circular dependency for module ‘tailf-ncs’

Files that are already part of NSO must not be included in the YANG
files when building a NED. This includes

* ietf-inet-types
* ietf-yang-types
* tailf-*

If one of the above files is included an error like the one below will
appear when building a NED from the YANG model:

    augmented/ietf-inet-types@2013-07-15.yang:8: error: circular dependency for module 'tailf-ncs'
    augmented/ietf-yang-types@2013-07-15.yang:8: error: circular dependency for module 'tailf-ncs'

Fix this by disabling the files with the issue and building the NED
again.

    devices device my-netconf-device pioneer yang disable name-pattern ietf-*-types
    Disabling module ietf-inet-types

# Contact

Contact Jan Lindblad <jlindbla@cisco.com> with any suggestions or
comments.
