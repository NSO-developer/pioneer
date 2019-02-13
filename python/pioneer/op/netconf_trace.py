# -*- mode: python; python-indent: 4 -*-

import os
import re
import time
import xml.etree.ElementTree

import io as StringIO

def _parse_time(time_str):
    time_millis = time_str.split('.')
    time_struct = time.strptime(time_millis[0], '%d-%b-%Y::%H:%M:%S')
    return time.mktime(time_struct)

def _parse_out(f_obj, line):
    log_time = _parse_time(line.split(' ')[1])
    message = StringIO.StringIO()

    skip_newline = False
    line = f_obj.readline()
    while len(line) > 0:
        line = line[:-1]

        if len(line) == 0:
            # ignore message chunk entry and spacing
            pass
        elif  line.startswith('>>>>out '):
            skip_newline = True
        elif line == 'EOM':
            return (log_time, message.getvalue())
        else:
            if skip_newline:
                skip_newline = False
            elif message.tell() > 0:
                message.write('\n')
            message.write(line)
        line = f_obj.readline()

    return (log_time, message.tell() > 0 and message.getvalue() or None)

def _parse_in(f_obj, line):
    log_time = _parse_time(line.split(' ')[1])
    message = StringIO.StringIO()

    in_hash = False
    skip_newline = False
    line = f_obj.readline()
    while len(line) > 0:
        line = line[:-1]

        if len(line) == 0:
            # ignore message chunk entry and spacing
            pass
        elif line.startswith('<<<<in '):
            # ignore message chunk entry
            skip_newline = True
        elif in_hash and line == '##':
            return (log_time, message.getvalue())
        elif re.match('#[0-9]+', line):
            in_hash = True
        else:
            if skip_newline:
                skip_newline = False
            elif message.tell() > 0:
                message.write('\n')
            if line.endswith(']]>]]>'):
                message.write(line[:-6])
                return (log_time, message.getvalue())
            message.write(line)

        line = f_obj.readline()

    return (log_time, message.tell() > 0 and message.getvalue() or None)

class LogMessage(object):
    def __init__(self, log_time, message, direction):
        self.time = log_time
        self.message = message
        self.direction = direction

class Parser(object):
    def __init__(self, f_obj, max_age_s):
        self.f_obj = f_obj
        self.max_age_s = max_age_s
        self.now = time.time()

    def __iter__(self):
        return self

    def next(self):
        line = self.f_obj.readline()
        while len(line) > 0:
            if line.startswith('>>>>out '):
                log_time, message = _parse_out(self.f_obj, line)
                if self._include_message(log_time, message):
                    return LogMessage(log_time, message, '>>>>')
            elif line.startswith('<<<<in '):
                log_time, message = _parse_in(self.f_obj, line)
                if self._include_message(log_time, message):
                    return LogMessage(log_time, message, '<<<<')
            line = self.f_obj.readline()

        raise StopIteration

    def _include_message(self, log_time, message):
        if message is None:
            return False
        if len(message) == 0:
            return False
        return self.max_age_s > (self.now - log_time)

def get_log_name():
    HEART_COMMAND = 'HEART_COMMAND'
    NS = '{http://tail-f.com/yang/tailf-ncs-config}'

    if HEART_COMMAND not in os.environ:
        return None

    # Not handling space in conffile argument, NSO does not currently
    # start with a path to config file with spaces.
    conf_files = re.findall('-conffile ([^ ]+)', os.environ[HEART_COMMAND])
    if len(conf_files) == 0:
        return None

    tree = xml.etree.ElementTree.parse(conf_files[0])
    root = tree.getroot()

    elems = root.findall('.//{0}netconf-log/{0}file/{0}name'.format(NS))
    if len(elems) == 0:
        return None

    return elems[0].text

def get_log_name_for_device(device):
    log_name = get_log_name()
    if log_name is None or not log_name.endswith('.log'):
        return None

    return '{0}-{1}.trace'.format(log_name[:-4], device)
