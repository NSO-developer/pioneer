# -*- mode: python; python-indent: 4 -*-

import fcntl
import os
import select
import subprocess
import sys
import time
import traceback

import _ncs.dp as dp
import _ncs.maapi as maapi
import _ncs.deprecated.maapi as dmaapi

from ex import ActionError
import pioneer.namespaces.pioneer_ns as ns

class BaseOp(object):
    ncs_dir = os.environ['NCS_DIR']
    pkg_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    ncs_run_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(pkg_root_dir))))
    ncs_rollback_dir = os.path.join(ncs_run_dir, "logs")
    states_dir = os.path.join(ncs_run_dir, "logs")
    
    def __init__(self, msocket, uinfo, dev_name, params, debug_func):
        self.msocket = msocket
        self.uinfo = uinfo
        self.dev_name = dev_name

        self.debug = debug_func
        
        self._init_params(params)

    def _init_params(self, params):
        # Implement in subclasses
        pass
    
    def param_default(self, params, tag, default):
        matching_param_list = [p.v for p in params if p.tag == tag]
        if len(matching_param_list) == 0:
            return default
        return str(matching_param_list[0])
    
    def extend_timeout(self, timeout_extension):
        dp.action_set_timeout(self.uinfo, timeout_extension)
        
    def proc_run_outputfun(self, command, timeout, outputfun):
        self.debug("run_outputfun '" + str(" ".join(command)))
        proc = subprocess.Popen(command,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        self.debug("run_outputfun, going in")
        fd = proc.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        state = None
        stdoutdata = ""
        while proc.poll() is None:
            rlist, wlist, xlist = select.select([fd], [], [fd], timeout)
            if rlist:
                buf = proc.stdout.read()
                if buf != "":
                    self.debug("run_outputfun, output len=" + str(len(buf)))
                    state = outputfun(state, buf)
                    stdoutdata += buf
            else:
                self.progress_msg("Silence timeout, terminating process\n")
                proc.kill()
                proc.wait()

        self.debug("run_finished, output len=" + str(len(stdoutdata)))
        return stdoutdata

    def proc_run(self, command, stdin_str="", timeout=10, outputfun=None):
        # Timeout is only used with outputfun
        self.debug("run '" + str(" ".join(command))
                     + "', input len=" + str(len(stdin_str)))
        try:
            if outputfun:
                return self.proc_run_outputfun(command, timeout, outputfun)
            else:
                proc = subprocess.Popen(command,
                                        stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
                (stdoutdata, stderrdata) = proc.communicate(input=stdin_str)
                self.debug("run finished, output len=" + str(len(stdoutdata))
                             + ", err len=" + str(len(stderrdata)))
                return (stdoutdata, stderrdata)
        except OSError as oserr:
            if oserr.errno == 2: # File not found
                raise ActionError({'error':"Dependent application not found, please install: " + str(command[0])})
            raise ActionError({'error':"OSError when executing " + str(command[0])})
        except:
            self.debug("run failed:\n" + repr(traceback.format_exception(*sys.exc_info())))
            raise ActionError({'error':"Failed to execute " + str(command[0])})

    def progress_msg(self, msg):
        self.debug(msg)
        maapi.cli_write(self.msocket, self.uinfo.usid, msg)

    def get_exe_path(self, exe):
        if exe == 'netconf-console':
            path = os.path.join(self.pkg_root_dir, "python", "pioneer", "netconf-console")
        else:
            path = self.get_exe_path_from_PATH(exe)

        if not os.path.exists(path):
            raise ActionError({'error':'Unable to execute {0}, command no found in PATH {1}'.format(exe, os.environ['PATH'])})

        return path

    def get_exe_path_from_PATH(self, exe):
        parts = (os.environ['PATH'] or '/bin').split(os.path.pathsep)
        for part in parts:
            path = os.path.join(part, exe)
            if os.path.exists(path):
                return path
        return None
