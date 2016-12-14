# -*- mode: python; python-indent: 4 -*-
"""
*********************************************************************
* (C) 2016 Tail-f Systems                                           *
* NETCONF/YANG PIONEER                                              *
*                                                                   *
* Your Swiss army knife when it somes to basic NETCONF,             *
* YANG module collection, NSO NETCONF NED building, installation    *
* and testing.                                                      *
*********************************************************************
"""

    ######################################################################
    ## IMPORTS & GLOBALS

from __future__ import print_function
import os
import sys
import select
import socket
import threading
import traceback

assert sys.version_info >= (2,7)
# Not tested with anything lower

import _ncs
import _ncs.dp as dp
import _ncs.maapi as maapi
import pioneer.namespaces.pioneer_ns as ns

XT = _ncs.XmlTag
V = _ncs.Value
TV = _ncs.TagValue
from ncs_pyvm import NcsPyVM
_schemas_loaded = False

# operation modules
import op.config_op
import op.log_op
import op.netconf_op
import op.yang_op
from op.ex import ActionError

def param_default(params, tag, default):
    matching_param_list = [p.v for p in params if p.tag == tag]
    if len(matching_param_list) == 0:
        return default
    return str(matching_param_list[0])

class ActionHandler(threading.Thread):
    handlers = {
        ns.ns.pioneer_delete_state: op.config_op.DeleteStateOp,
        ns.ns.pioneer_explore_transitions: op.config_op.ExploreTransitionsOp,
        ns.ns.pioneer_import_into_file: op.config_op.ImportIntoFileOp,
        ns.ns.pioneer_list_states: op.config_op.ListStatesOp,
        ns.ns.pioneer_record_state: op.config_op.RecordStateOp,
        ns.ns.pioneer_sync_from_into_file: op.config_op.SyncFromIntoFileOp,
        ns.ns.pioneer_transition_to_state: op.config_op.TransitionToStateOp,
        ns.ns.pioneer_hello: op.netconf_op.HelloOp,
        ns.ns.pioneer_get: op.netconf_op.GetOp,
        ns.ns.pioneer_get_config: op.netconf_op.GetConfigOp,
        ns.ns.pioneer_build_netconf_ned: op.yang_op.BuildNetconfNedOp,
        ns.ns.pioneer_disable: op.yang_op.DisableOp,
        ns.ns.pioneer_download: op.yang_op.DownloadOp,
        ns.ns.pioneer_enable: op.yang_op.EnableOp,
        ns.ns.pioneer_fetch_list: op.yang_op.FetchListOp,
        ns.ns.pioneer_show_list: op.yang_op.ShowListOp,
        ns.ns.pioneer_check_dependencies: op.yang_op.CheckDependenciesOp,
        ns.ns.pioneer_delete: op.yang_op.DeleteOp,
        ns.ns.pioneer_build_netconf_ned: op.yang_op.BuildNetconfNedOp,
        ns.ns.pioneer_install_netconf_ned: op.yang_op.InstallNetconfNedOp,
        ns.ns.pioneer_uninstall_netconf_ned: op.yang_op.UninstallNetconfNedOp,
        ns.ns.pioneer_sftp: op.yang_op.SftpOp,
        ns.ns.pioneer_print_netconf_trace: op.log_op.PrintNetconfTraceOp
    }

    ######################################################################
    ##  CB_ACTION  #######################################################
    ######################################################################

    def cb_action(self, uinfo, op_name, kp, params):
        self.debug("========== pioneer cb_action() ==========")

        dev_name = str(kp[-3][0])
        self.debug("thandle={0} usid={1}".format(uinfo.actx_thandle, uinfo.usid))
        
        try:
            if op_name.tag not in self.handlers:
                raise ActionError({'error': "Operation not implemented: {0}".format(op_name)})
            
            handler_cls = self.handlers[op_name.tag]
            handler = handler_cls(self.msocket, uinfo, dev_name, params, self.debug)
            result = handler.perform()
            return self.action_response(uinfo, result)

        ##----------------------------------------------------------------
        except ActionError as ae:
            self.debug("ActionError exception")
            return self.action_response(uinfo, ae.get_info())
        except:
            self.debug("Other exception: " + repr(traceback.format_exception(*sys.exc_info())))
            msg = "Operation failed"
            dp.action_reply_values(uinfo, [TV(XT(ns.ns.hash, ns.ns.pioneer_error), V(msg))])
            return _ncs.CONFD_OK

    def action_response(self, uinfo, result):
        reply = []

        if result.has_key('message'):
            reply += [TV(XT(ns.ns.hash, ns.ns.pioneer_message), V(result['message']))]
        if result.has_key('error'):
            reply += [TV(XT(ns.ns.hash, ns.ns.pioneer_error), V(result['error']))]
        if result.has_key('success'):
            reply += [TV(XT(ns.ns.hash, ns.ns.pioneer_success), V(result['success']))]
        if result.has_key('failure'):
            reply += [TV(XT(ns.ns.hash, ns.ns.pioneer_failure), V(result['failure']))]
        if result.has_key('filename'):
            reply += [TV(XT(ns.ns.hash, ns.ns.pioneer_filename), V(result['filename']))]
        if result.has_key('ned-directory'):
            reply += [TV(XT(ns.ns.hash, ns.ns.pioneer_ned_directory), V(result['ned-directory']))]
        if result.has_key('yang-directory'):
            reply += [TV(XT(ns.ns.hash, ns.ns.pioneer_yang_directory), V(result['yang-directory']))]
        if result.has_key('missing'):
            reply += [TV(XT(ns.ns.hash, ns.ns.pioneer_missing), V(result['missing']))]
        if result.has_key('enabled'):
            reply += [TV(XT(ns.ns.hash, ns.ns.pioneer_enabled), V(result['enabled']))]
        if result.has_key('disabled'):
            reply += [TV(XT(ns.ns.hash, ns.ns.pioneer_disabled), V(result['disabled']))]
        if result.has_key('marked'):
            reply += [TV(XT(ns.ns.hash, ns.ns.pioneer_marked), V(result['marked']))]
        if result.has_key('get-config-reply'):
            reply += [TV(XT(ns.ns.hash, ns.ns.pioneer_get_config_reply), V(result['get-config-reply']))]
        if result.has_key('get-reply'):
            reply += [TV(XT(ns.ns.hash, ns.ns.pioneer_get_reply), V(result['get-reply']))]
        if result.has_key('hello-reply'):
            reply += [TV(XT(ns.ns.hash, ns.ns.pioneer_hello_reply), V(result['hello-reply']))]
            self.debug("action reply={0}".format(reply))

        dp.action_reply_values(uinfo, reply)
        return _ncs.CONFD_OK
            
    ######################################################################
    ##  REGISTRATION  ####################################################
    ######################################################################
            
    def __init__(self, debug, pipe):
        threading.Thread.__init__(self)
        self.debug = debug
        self.pipe = pipe
        
    def run(self):
        self.debug("Starting worker...")
        self.csocket = socket.socket()
        self.wsocket = socket.socket()
        self.msocket = socket.socket()

        ctx = dp.init_daemon("pioneer")

        dp.connect(
            dx=ctx,
            sock=self.csocket,
            type=dp.CONTROL_SOCKET,
            ip='127.0.0.1',
            port=_ncs.NCS_PORT
        )
        dp.connect(
            dx=ctx,
            sock=self.wsocket,
            type=dp.WORKER_SOCKET,
            ip='127.0.0.1',
            port=_ncs.NCS_PORT
        )
        maapi.connect(
            sock=self.msocket,
            ip='127.0.0.1',
            port=_ncs.NCS_PORT
        )

        dp.install_crypto_keys(ctx)
        dp.register_action_cbs(ctx, 'pioneer', self)
        dp.register_done(ctx)

        _r = [self.csocket, self.wsocket, self.pipe]
        _w = []
        _e = []

        while True:
            (r, w, e) = select.select(_r, _w, _e)

            if self.csocket in r:
                dp.fd_ready(ctx, self.csocket)
            if self.wsocket in r:
                dp.fd_ready(ctx, self.wsocket)
            if self.pipe in r:
                # We will only get something through the pipe when it is time to
                # quit so we break and jump out of the loop.
                break

        self.wsocket.close()
        self.csocket.close()
        dp.release_daemon(ctx)

        self.debug("Worker stopped")

    def cb_init(self, uinfo):
        dp.action_set_fd(uinfo, self.wsocket)

# ---------------------------------------------
# COMPONENT THREAD THAT WILL BE STARTED BY NCS.
# ---------------------------------------------

class Action(object):

    def __init__(self, *args, **kwds):
        # Setup the NCS object, containing mechanisms
        # for communicating between NCS and this User code.
        self._ncs = NcsPyVM(*args, **kwds)

        # Just checking if the NCS logging works...
        self.debug('Initalizing object')

        # Register our 'finish' callback
        self._finish_cb = lambda: self.finish()
        self._ncs.reg_finish(self._finish_cb)
        self.mypipe = os.pipe()

        self.waithere = threading.Semaphore(0)  # Create as blocked

    # This method starts the user application in a thread
    def run(self):
        global _schemas_loaded

        self.debug("action.py:run starting")
        #if _schemas_loaded is False:
        if False: # No schema loading for now
            try:
                ms = socket.socket()
                maapi.connect(sock=ms, ip='127.0.0.1',
                            port=_ncs.NCS_PORT)
                #maapi.load_schemas(ms)
                ms.close()
                _schemas_loaded = True
            except:
                self.debug("Exception: "+ str(sys.exc_info()[0]))
                
        self.debug("run: starting action handler...")
        w = ActionHandler(self.debug,
                          self.mypipe[0])

        # Since the ActionHandler object above is a thread, when we call the
        # start method the Thread class will invoke the
        # ActionHandler.run-method.
        w.start()
        self.debug("action.py:run: starting worker...")
        self._ncs.add_running_thread('Worker')

        # Wait here until 'finish' gets called
        self.debug("action.py:run: waiting for work...")
        self.waithere.acquire()

        # Inform the 'subscriber' that it has to shutdown
        os.write(self.mypipe[1], 'finish')
        self.debug("action.py:run: finished...")

    # Just a convenient logging function
    def debug(self, line):
        self._ncs.debug(line)

    # Callback that will be invoked by NCS when the system is shutdown.
    # Make sure to shutdown the User code, including any User created threads.
    def finish(self):
        self.waithere.release()

    ######################################################################
