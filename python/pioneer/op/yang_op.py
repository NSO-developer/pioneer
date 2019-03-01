# -*- mode: python; python-indent: 4 -*-

import fnmatch
import os
import re
import shutil
import socket
import time
import traceback

import _ncs
import _ncs.maapi as maapi

import pioneer.op.netconf_op as netconf_op
import pioneer.namespaces.pioneer_ns as ns

from pioneer.op.ex import ActionError

class YangOp(netconf_op.NetconfOp):

    def _init_params(self, params):
        netconf_op.NetconfOp._init_params(self, params)
        self.yang_directory = self.param_default(params, ns.ns.pioneer_yang_directory, os.path.join("/tmp/download", self.dev_name))

    def create_yang_dir(self):
        try:
            os.makedirs(self.yang_directory)
        except:
            pass
        if not os.path.exists(self.yang_directory):
            raise ActionError({'error': 'Failed to create directory {0}'.format(self.yang_directory)})

    def list_models_in_dir(self, cat='enabled'):
        if(cat == 'marked'):
            return [f[:-9] for f in os.listdir(self.yang_directory) if fnmatch.fnmatch(f, '*.yang.yes')]
        if(cat == 'disabled'):
            return [f[:-8] for f in os.listdir(self.yang_directory) if fnmatch.fnmatch(f, '*.yang.no')]
        if(cat == 'enabled'):
            return [f[:-5] for f in os.listdir(self.yang_directory) if fnmatch.fnmatch(f, '*.yang')]
        if(cat == 'builtin'):
            return [f[:-5] for f in os.listdir(self.ncs_dir + "/src/ncs/yang") if fnmatch.fnmatch(f, '*.yang')]
        return []

    def list_models_in_file(self, file_name):
        if file_name is None:
            return []

        try:
            with open(file_name, "r") as f_obj:
                return f_obj.read().split('\n')
        except:
            return []

    def parse_name_list(self, name):
        return [m for m in (name.replace(" ", "\n") + "\n").split("\n") if m != ""]

    def make_yang_mark_file(self, modname):
        yang_file_name = self.yang_directory + "/" + modname + ".yang.yes"
        with open(yang_file_name, "w") as m:
            m.write("")

class DownloadOp(YangOp):
    tag = ns.ns.pioneer_download

    def _init_params(self, params):
        YangOp._init_params(self, params)
        self.name = self.param_default(params, ns.ns.pioneer_include_names, '')
        self.file = self.param_default(params, ns.ns.pioneer_include_names_in_file, '')

    def perform(self):
        self.debug("yang_download() with device {0}".format(self.dev_name))
        self.create_yang_dir()

        model_list = self.parse_name_list(self.name)
        model_list += self.list_models_in_file(self.file)
        model_list += self.list_models_in_dir('marked')
        self.debug("Processing list 2 " + str(model_list))
        files_tot = len(model_list)
        if 0 == files_tot:
            return {'yang-directory':self.yang_directory,
                    'error':"No files marked for download; did you forget to run fetch-list?"}
        self.progress_msg("Downloading {0} modules to {1}\n".format(files_tot,self.yang_directory))
        downloaded_count = 0
        failed_count = 0
        skipped_count = 0
        file_no = 0
        result_str = ""
        for modname in model_list:
            file_no += 1
            yang_file_name = self.yang_directory + "/" + modname + ".yang"
            self.debug("FQFN " + yang_file_name)
            if os.path.exists(yang_file_name) or os.path.exists(yang_file_name + ".no"):
                skipped_count += 1
                self.debug("Module already downloaded, skipping " + modname)
                self.progress_msg("Skipping module " + modname + " -- already downloaded\n")
                continue
            self.debug("Downloading module " + modname)
            self.progress_msg("{0}/{1} Downloading module {2} ".
                              format(file_no, files_tot, modname))
            self.extend_timeout(180) # Max 180 seconds per file, ok?
            try:
                xml_module = self.nc_perform('get-schema', method_opts=[str(modname)])
            except Exception as e:
                self.progress_msg("-- download failed\n")
                result_str += "Failed {0} fetch error '{1}'\n".format(modname, repr(e))
                failed_count += 1
            else:
                self.extend_timeout(90) # Max 90 seconds per file, ok?
                (yang_module, stderr) = self.proc_run([self.get_exe_path("xsltproc"),
                                                       "--nonet", "--novalid",
                                                       self.pkg_root_dir + "/load-dir/ncs-extract-module.xsl",
                                                       "-"],
                                                      xml_module)
                self.debug("Parsed module:\n" + yang_module + "\n" + stderr)
                if yang_module == "ERROR":
                    self.progress_msg(" -- failed, not found\n")
                    result_str += "Failed {0} rpc error\n".format(modname)
                    failed_count += 1
                elif stderr != "":
                    self.progress_msg(" -- parsing failed\n")
                    result_str += "Failed {0} parse error '{1}'\n".format(modname, stderr)
                    failed_count += 1
                else:
                    try:
                        with open(yang_file_name, "w") as m:
                            m.write(yang_module)
                        self.progress_msg(" -- succeeded\n")
                        result_str += "Downloaded {0}\n".format(modname)
                        downloaded_count += 1
                        if os.path.exists(yang_file_name + ".yes"):
                            os.remove(yang_file_name + ".yes")
                    except:
                        self.progress_msg(" -- writing file failed\n")
                        result_str += "Failed {0} write error\n".format(modname)
                        failed_count += 1
        self.debug("Model download done")
        message = "Downloaded {0} modules, failed {1}, skipped {2}:\n{3}".format(
            downloaded_count, failed_count, skipped_count, result_str)
        return {'yang-directory':self.yang_directory, 'message':message}

class DisableOp(YangOp):
    def _init_params(self, params):
        YangOp._init_params(self, params)
        self.name_pattern = self.param_default(params, ns.ns.pioneer_name_pattern, "").split(' ')

    def perform(self):
        self.debug("yang_disable() with device {0}".format(self.dev_name))
        if not os.path.exists(self.yang_directory):
            return {'error':"Failed to find source directory " + self.yang_directory}
        yangs = self.list_models_in_dir()
        yangs.extend(self.list_models_in_dir('marked'))
        builtin_yangs = self.list_models_in_dir('builtin')
        message = ""
        for yang in yangs:
            self.debug("Check disable "+ yang + " name-pattern="+str(self.name_pattern))
            if [sp for sp in self.name_pattern if fnmatch.fnmatch(yang, sp)] or (self.name_pattern == [''] and yang in builtin_yangs):
                self.debug("Disabling "+ yang)
                message += "Disabling module {0}\n".format(yang)
                # Renaming file to .yang.no
                enabled_fq_yang = os.path.join(self.yang_directory, '{0}.yang'.format(yang))
                disabled_fq_yang = '{0}.no'.format(enabled_fq_yang)
                if not os.path.exists(enabled_fq_yang):
                    enabled_fq_yang += ".yes"
                os.rename(enabled_fq_yang, disabled_fq_yang)
        if "" == message:
            return {'error':"No modules matching pattern"}
        else:
            return {'success':message}

class EnableOp(YangOp):
    def _init_params(self, params):
        YangOp._init_params(self, params)
        self.name_pattern = self.param_default(params, ns.ns.pioneer_name_pattern, "*").split(' ')

    def perform(self):
        self.debug("yang_enable() with device {0}".format(self.dev_name))
        if not os.path.exists(self.yang_directory):
            return {'error':"Failed to find source directory " + self.yang_directory}
        disabled_yangs = self.list_models_in_dir('disabled')
        message = ""
        for yang in disabled_yangs:
            if [sp for sp in self.name_pattern if fnmatch.fnmatch(yang, sp)]:
                self.debug("Enabling "+ yang)
                message += "Enabling module {0}\n".format(yang)
                enabled_fq_yang = os.path.join(self.yang_directory, '{0}.yang'.format(yang))
                disabled_fq_yang = '{0}.no'.format(enabled_fq_yang)
                # 0 bytes disabled file is treated as a result from
                # fetch-list to avoid re-downloading modules everytime
                # download is called
                if os.path.getsize(disabled_fq_yang) == 0:
                    enabled_fq_yang += '.yes'
                os.rename(disabled_fq_yang, enabled_fq_yang)
        return {'success':message}

class FetchListOp(YangOp):
    def perform(self):
        self.debug("yang_fetch_list() with device {0}".format(self.dev_name))
        self.create_yang_dir()
        self.progress_msg("Retrieving module list from device\n")
        self.extend_timeout(180) # Max 180 seconds for hello, ok?
        hello = self.nc_perform('hello')
        capas = self.extract_capas_from_hello(hello)
        model_list_hello = self.extract_model_list_from_hello(capas)
        if self.device_has_capa_netconf_monitoring(capas):
            self.progress_msg("Device supports netconf-monitoring\n")
        else:
            self.progress_msg("Device does not report support for netconf-monitoring, trying anyway\n")
        self.extend_timeout(180) # Max 180 seconds for model fetch, ok?
        model_list_subtree = self.fetch_model_list_netconf_monitoring('subtree')
        self.extend_timeout(180) # Max 180 seconds for model fetch, ok?
        model_list_xpath = self.fetch_model_list_netconf_monitoring('xpath')

        model_list = model_list_hello + model_list_subtree + model_list_xpath

        mods={}
        for modname in model_list:
            mods[modname] = 1
        self.debug("Processing list 2 " + str(mods))
        self.progress_msg(
"""
Found out the names for a total of {0} modules
hello message: {1}
netconf-monitoring subtree: {2}
netconf-monitoring xpath: {3}
""".
                        format(len(mods), len(model_list_hello),
                               len(model_list_subtree), len(model_list_xpath)))
        marked_count = 0
        skipped_count = 0
        for modname in mods:
            yang_file_name = self.yang_directory + "/" + modname + ".yang"
            self.debug("FQFN " + yang_file_name)
            if os.path.exists(yang_file_name) or os.path.exists(yang_file_name + ".no"):
                skipped_count += 1
                self.debug("Module already downloaded or disabled, skipping " + modname)
                self.progress_msg("Skipping module " + modname + " -- already downloaded/disabled\n")
                continue
            self.progress_msg("Marked module " + modname + " for download\n")
            self.make_yang_mark_file(modname)
            marked_count += 1
        self.debug("Model list fetch done")
        message = "Marked {0} modules for download, skipped {1}".format(
            marked_count, skipped_count)

        return {'yang-directory':self.yang_directory, 'message':message}

class ShowListOp(YangOp):
    def perform(self):
        self.debug("yang_show_list() with device {0}".format(self.dev_name))
        if not os.path.exists(self.yang_directory):
            return {'error':"Failed to find source directory " + self.yang_directory}

        reply = {}
        enabled_yangs  = self.list_models_in_dir()
        if len(enabled_yangs) != 0:
            reply['enabled'] = "\n".join(["===== ENABLED ====="] + enabled_yangs)
        disabled_yangs = self.list_models_in_dir('disabled')
        if len(disabled_yangs) != 0:
            reply['disabled'] = "\n".join(["===== DISABLED ====="] + disabled_yangs)
        marked_yangs = self.list_models_in_dir('marked')
        if len(marked_yangs) != 0:
            reply['marked'] = "\n".join(["===== MARKED ====="] + marked_yangs)

        return reply

class CheckDependenciesOp(YangOp):
    def perform(self):
        self.debug("yang_check_dependencies() with device {0}".format(self.dev_name))
        enabled_yangs = self.list_models_in_dir()
        disabled_yangs = self.list_models_in_dir('disabled')
        missing_files = {}
        items = len(enabled_yangs)
        item = 0
        for yang in enabled_yangs:
            item += 1
            self.progress_msg("{0}/{1} checking {2}: ".format(item, items, yang))
            self.extend_timeout(180) # Max 3 mins per file, ok?
            #'pyang' must be in PATH before using pioneer
            (depend_txt, stderr) = self.proc_run(["pyang",
                              "-f", "depend",
                              "--path", self.yang_directory,
                              self.yang_directory + "/" + yang + ".yang"])
            compiler_output = depend_txt + "\n" + stderr
            self.debug("dependencies:\n" + compiler_output)
            for line in compiler_output.split("\n"):
                self.debug("line " + str(line) + "\n")
                err_msg_parts = line.split("error: ")

                self.debug("err_msg_parts " + str(err_msg_parts) + "\n")
                if len(err_msg_parts) == 2:
                    module_msg_parts = err_msg_parts[1].split('"')
                    if module_msg_parts[0] == "module " and module_msg_parts[2] == " not found in search path":
                        missing_modname = module_msg_parts[1]
                        missing_files[missing_modname] = 1
                        if missing_modname not in disabled_yangs:
                            self.progress_msg(missing_modname + " ")
                            self.make_yang_mark_file(missing_modname)
                        else:
                            self.progress_msg("(" + missing_modname + ") ")

            self.progress_msg("\n")
        if len(missing_files) == 0:
            return {'success':"The set of {0} enabled yang files seems consistent".
                    format(len(enabled_yangs))}
        return {'missing':" ".join(missing_files.keys()),
                'failure':"The set of {0} enabled yang files are missing {1} files".
                    format(len(enabled_yangs), len(missing_files))}

class DeleteOp(YangOp):
    def _init_params(self, params):
        YangOp._init_params(self, params)
        self.name_pattern = self.param_default(params, ns.ns.pioneer_name_pattern, "")

    def perform(self):
        self.debug("yang_delete() with device {0}".format(self.dev_name))
        if not os.path.exists(self.yang_directory):
            return {'error':"Failed to find source directory " + self.yang_directory}
        enabled_yangs = self.list_models_in_dir()
        disabled_yangs = self.list_models_in_dir('disabled')
        marked_yangs = self.list_models_in_dir('marked')
        message = ""
        for yang in enabled_yangs + disabled_yangs + marked_yangs:
            if [sp for sp in self.name_pattern.split(' ') if fnmatch.fnmatch(yang, sp)]:
                self.debug("Deleting "+ yang + " name-pattern="+str(self.name_pattern))
                message += "Deleting module {0}\n".format(yang)
                for f in [self.yang_directory + "/" + f for f in os.listdir(self.yang_directory) if fnmatch.fnmatch(f, yang + ".yang*")]:
                    self.debug("Deleting "+ f)
                    os.remove(f)
        return {'success':message}

class BuildNetconfNedOp(YangOp):
    def _init_params(self, params):
        YangOp._init_params(self, params)
        self.name = self.param_default(params, ns.ns.pioneer_name, self.dev_name)
        self.ned_directory = self.param_default(params, ns.ns.pioneer_ned_directory, "/tmp/packages/" + self.name)
        self.silence_timeout = int(self.param_default(params, ns.ns.pioneer_silence_timeout, "60"))

    def perform(self):
        self.debug("yang_build_netconf_ned() with device {0}".format(self.dev_name))
        if not os.path.exists(self.yang_directory):
            return {'error':"Failed to find source directory " + self.yang_directory}
        try:
            os.makedirs(self.ned_directory)
        except:
            pass
        if not os.path.exists(self.ned_directory):
            return {'error':"Failed to create ned directory " + self.ned_directory}
        yang_dir = self.ned_directory + "/src/yang"
        if os.path.exists(yang_dir):
            self.progress_msg("Cleaning up existing ned-directory\n")
            [ os.remove(yang_dir + "/" + f) for f in os.listdir(yang_dir) if f.endswith(".yang") ]
        enabled_yangs  = self.list_models_in_dir()
        num_yangs = len(enabled_yangs)
        self.progress_msg("Starting build of {0} YANG modules, this may take some time\n".format(num_yangs))
        self.extend_timeout(60) # Start with max 60 secs silence, ok?
        ## FIXME
        def build_progress_fun(state, stdout):
            self.progress_msg(stdout)
            self.extend_timeout(120)
            return None

        build_output = self.proc_run([self.get_exe_path('bash'),
                                      self.pkg_root_dir + "/python/pioneer/ncs-make-package-verbose",
                                      self.yang_directory, self.name, self.ned_directory],
                                     timeout=self.silence_timeout,
                                     outputfun=build_progress_fun)
        self.debug("Output from build\n{0}\n".format(build_output))

        if os.path.exists(self.ned_directory + "/src/ncsc-out/.done"):
            self.progress_msg("Build complete. Run install-netconf-ned, then run 'packages reload' to use the package")
            return {'ned-directory':self.ned_directory}
        else:
            stdout_issues = "\n".join([str(line) for line in build_output.split('\n') if re.search(r"(?i)\berror|\bwarning", line)])
            self.progress_msg("Build failed. Error and warning messages below. See log for complete details\n{0}\n".format(stdout_issues))
        return {'failure':'Build failed'}

class InstallOpBase(YangOp):
    def _init_params(self, params):
        YangOp._init_params(self, params)
        self.name = self.param_default(params, ns.ns.pioneer_name, self.dev_name)
        self.nso_runtime_directory = self.param_default(params, ns.ns.pioneer_nso_runtime_directory, os.getcwd())
        self.ned_directory = self.param_default(params, ns.ns.pioneer_ned_directory, "/tmp/packages/" + self.name)

    def save_old_ned_package(self):
        package_dir_name = self.nso_runtime_directory + "/packages/" + self.name
        if os.path.exists(package_dir_name):
            (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = os.stat(package_dir_name)
            timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(mtime))
            bak_name = self.nso_runtime_directory + "/old-packages/" + self.name + "-{0}".format(timestamp)
            self.progress_msg("Old package exists, moving to {0}\n".format(bak_name))
            self.extend_timeout(30) # Max another 30 secs, ok?
            shutil.move(package_dir_name, bak_name)
            return (package_dir_name, bak_name)
        return (package_dir_name, None)

class InstallNetconfNedOp(InstallOpBase):
    def perform(self):
        self.debug("yang_install_netconf_ned() with device {0}".format(self.dev_name))
        if not os.path.exists(self.ned_directory + "/src/ncsc-out/.done"):
            return {'failure':'The package is not successfully built, installation canceled'}
        (package_dir_name, bak_name) = self.save_old_ned_package()
        self.progress_msg("Copying new package into {0}\n".format(package_dir_name))
        self.extend_timeout(30) # Max another 30 secs, ok?
        shutil.copytree(self.ned_directory, package_dir_name)
        return {'success':'Installed -- now you need to: packages reload'}

class UninstallNetconfNedOp(InstallOpBase):
    def perform(self):
        self.debug("yang_uninstall_netconf_ned() with device {0}".format(self.dev_name))
        (package_dir_name, bak_name) = self.save_old_ned_package()
        if bak_name == None:
            return {'error':'No NED installed in ' + package_dir_name}
        return {'success':'Old NED package moved to ' + bak_name}

class SftpOp(YangOp):
    def _init_params(self, params):
        YangOp._init_params(self, params)
        self.remote_path = self.param_default(params, ns.ns.pioneer_remote_path, "")
        self.name = self.param_default(params, ns.ns.pioneer_include_names, "")

    def perform(self):
        self.debug("yang_sftp() with device {0}".format(self.dev_name))
        self.create_yang_dir()

        try:
            import paramiko
        except ImportError:
            raise ActionError({'error':"SFTP support requires paramiko to be available"})

        host, port, username, password, rsa_key_path = self._yang_sftp_read_settings()

        model_list = self.parse_name_list(self.name)
        match = lambda n: (len(model_list) == 0) or (n in model_list)

        self.debug('connecting to {0}:{1} as {2}...'.format(host, port, username))
        message = 'connection failed'
        try:
            with paramiko.Transport((host, port)) as transport:
                if password is None:
                    pkey = paramiko.RSAKey.from_private_key_file(rsa_key_path)
                    transport.connect(username=username, pkey=pkey)
                else:
                    transport.connect(username=username, password=password)

                with paramiko.SFTPClient.from_transport(transport) as sftp:
                    names = [name for name in sftp.listdir(self.remote_path)
                             if name.endswith('.yang') and match(name)]
                    self.progress_msg("Downloading {0} files using SFTP...\n".format(len(names)))
                    for name in names:
                        remote_path = '{0}/{1}'.format(self.remote_path, name)
                        local_path = os.path.join(self.yang_directory, name)
                        sftp.get(remote_path, local_path)
                    message = 'transferred {0} files'.format(len(names))
        except Exception as e:
            message = 'error occured {0}'.format(e)
            self.debug(message)
            self.debug(traceback.format_exc())

        return {'yang-directory':self.yang_directory, 'message':message}

    def _yang_sftp_read_settings(self):
        def safe_get(sock, th, path, default=None):
            try:
                return maapi.get_elem(sock, th, path)
            except _ncs.error.Error as e:
                if e.confd_errno == _ncs.ERR_NOEXISTS:
                    if isinstance(default, Exception):
                        raise default
                    return default
                else:
                    raise e

        sock = socket.socket()
        maapi.connect(sock, '127.0.0.1', _ncs.PORT)
        try:
            maapi.start_user_session2(sock, 'admin', 'system', [], '127.0.0.1', 0, _ncs.PROTO_TCP)
            try:
                th = maapi.start_trans(sock, _ncs.RUNNING, _ncs.READ)

                sftp_prefix = '/{0}:{1}/{2}/'.format(
                    ns.ns.prefix, ns.ns.pioneer_pioneer_, ns.ns.pioneer_sftp_)
                host_path = sftp_prefix + ns.ns.pioneer_host_
                host = safe_get(sock, th, host_path,
                                ActionError({'error': host_path + ' is required'}))
                port = safe_get(sock, th, sftp_prefix + ns.ns.pioneer_port_, 22)
                username_path = sftp_prefix + ns.ns.pioneer_username_
                username = safe_get(sock, th, username_path,
                                    ActionError({'error': username_path + ' is required'}))
                password = safe_get(sock, th, sftp_prefix + ns.ns.pioneer_password_, None)

                rsa_key_path = safe_get(sock, th, sftp_prefix + ns.ns.pioneer_rsa_key_path_, '~/id_rsa')

                return (str(host), int(port), str(username), password and str(password) or None, os.path.expanduser(str(rsa_key_path)))
            finally:
                maapi.end_user_session(sock)
        finally:
            sock.close()
