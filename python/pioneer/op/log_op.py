# -*- mode: python; python-indent: 4 -*-

import os
import time

import pioneer.namespaces.pioneer_ns as ns

import base_op
import netconf_trace

class LogOp(base_op.BaseOp):
    pass

class PrintNetconfTraceOp(LogOp):
    def _init_parms(self, params):
        self.max_age_s = int(self.param_default(params, ns.ns.pioneer_max_age_s, "120"))

    def perform(self):
        self.debug("log_print_netconf_trace() with device {0}".format(self.dev_name, ))

        log_path = netconf_trace.get_log_name_for_device(self.dev_name)
        if log_path is None:
            return {'error': 'unable to determine log path'}

        if not os.path.exists(log_path):
            return {'message': 'no log file available, is netconf tracing enabled?'}

        num = 0
        with open(log_path, "r") as f_obj:
            for entry in netconf_trace.Parser(f_obj, self.max_age_s):
                num += 1
                self.progress_msg("{0} {1}\n{2}\n\n".format(
                    entry.direction,
                    time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry.time)),
                    entry.message))

        return {'success': '%d entries matched' % (num, )}

