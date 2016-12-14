# -*- mode: python; python-indent: 4 -*-

import sys

import _ncs
import _ncs.deprecated.maapi as dmaapi

from ex import ActionError

import base_op
import pioneer.namespaces.pioneer_ns as ns

class NetconfOp(base_op.BaseOp):
    def get_conn_details(self):
        def safe_ncs_decrypt(value):
            if value is None:
                return None
            try:
                return _ncs.decrypt(len=255, ciphertext=value)
            except:
                return _ncs.decrypt(ciphertext=value)
        
        with dmaapi.wctx.connect(ip = '127.0.0.1', port = _ncs.NCS_PORT) as c :
            with dmaapi.wctx.session(c, 'admin') as s :
                with dmaapi.wctx.trans(s, readWrite = _ncs.READ_WRITE) as t :
                    device_path = '/ncs:devices/device{"' + self.dev_name + '"}'
                    address = str(t.get_elem(device_path + '/address'))
                    device_type_netconf = t.exists(device_path + '/device-type/netconf')
                    try:
                        port = int(t.get_elem(device_path + '/port'))
                    except:
                        port = 830
                    self.debug("Device addr={0}, port={1}, netconf={2}".
                                 format(address, port, device_type_netconf))
                    if device_type_netconf != True:
                        raise ActionError({'error':"pioneer only works with NETCONF devices"})

                    authgroup_name = str(t.get_elem(device_path + '/authgroup'))
                    authgroup_path = '/ncs:devices/authgroups/group{"' + authgroup_name + '"}/default-map' ## FIXME default-map only, add umap support -- or at least an error message

                    missing = []
                    try:
                        remote_name = str(t.get_elem(authgroup_path + '/remote-name'))
                    except:
                        missing.append('remote-name')
                    try:
                        remote_password = str(t.get_elem(authgroup_path + '/remote-password')) # FIXME password only
                    except:
                        missing.append('remote-password')

                    if len(missing) > 0:
                        raise ActionError({'error': 'required configuration in authentication group {0} default-map missing: {1}'.format(
                            authgroup_name, ', '.join(missing))})

                    self.debug("Credentials user={0}, pass={1}".format(remote_name, remote_password))
                    remote_password = safe_ncs_decrypt(remote_password)

                    return (address, port, remote_name, remote_password)

    def device_has_capa_netconf_monitoring(self, capas_list):
        return ("urn:ietf:params:xml:ns:yang:ietf-netconf-monitoring" in capas_list)

    def module_name_from_capa(self, string):
        # Pick out the actual module name "Cisco-IOS-XR-bundlemgr-oper" from a capas line that might look like this:
        # http://cisco.com/ns/yang/Cisco-IOS-XR-bundlemgr-oper?module=Cisco-IOS-XR-bundlemgr-oper&revision=2015-11-09
        return string.split("?module=")[1].split("&")[0]
    
    def extract_model_list_from_hello(self, capas):
        self.debug("Hello capas len:\n" + str(len(capas)))
        model_list = [self.module_name_from_capa(c) for c in capas if (c.find("?module=") >= 0)]
        self.debug("Hello model len:\n" + str(len(model_list)))
        self.debug("Hello model list:\n" + str(model_list))
        return model_list

    def extract_capas_from_hello(self,  hello_str):
        self.debug("Parsing capas")
        (capas_list_txt, stderr) = self.proc_run([self.get_exe_path("xsltproc"),
                                                  "--nonet", "--novalid",
                                                  self.pkg_root_dir + "/load-dir/ncs-extract-capas.xsl",
                                                  "-"],
                                                 hello_str)
        self.debug("Parsed:\n" + capas_list_txt + "\n" + stderr)
        if stderr != "":
            raise ActionError({'error':"Failed to parse capas list:\n" + stderr})
        capas_list=capas_list_txt.split("\n")
        return capas_list
    
    def nc_perform(self, op='get', subtree='', xpath='', method_opts=None):
        if subtree != '':
            method_opts = [ "--subtree", subtree ]
        elif xpath != '':
            method_opts = [ "--xpath", xpath ]
        elif method_opts is None:
            method_opts = []

        (address, port, remote_name, remote_password) = self.get_conn_details()
        (xml_get_result, stderr) = self.proc_run([sys.executable,
                                                  self.get_exe_path('netconf-console'),
                                                  "--"+op ] + method_opts +
                                                 ["--host="+str(address),
                                                  "--port="+str(port),
                                                  "--user="+str(remote_name),
                                                  "--password="+str(remote_password)])
        self.debug("Fetched:\n" + xml_get_result + "\n\n" + stderr)
        if stderr != "":
            raise ActionError({'error':"Failed to execute "+op+":\n" + stderr})
        return xml_get_result

    def fetch_model_list_netconf_monitoring(self, method):
        if method == 'subtree':
            self.debug("Fetching YANG model list with netconf-console --get --subtree from netconf-monitoring")
            xml_get_result = self.nc_perform(subtree="<netconf-state xmlns='urn:ietf:params:xml:ns:yang:ietf-netconf-monitoring'/>")
        else:
            self.debug("Fetching YANG model list with netconf-console --get --xpath from netconf-monitoring")
            xml_get_result = self.nc_perform(xpath="/netconf-state")

        self.debug("Parsing model names")
        (model_list_txt, stderr) = self.proc_run([self.get_exe_path("xsltproc"),
                                                  "--nonet", "--novalid",
                                                  self.pkg_root_dir + "/load-dir/ncs-extract-schemas.xsl",
                                                  "-"],
                                                 xml_get_result)
        self.debug("Parsed:\n" + model_list_txt + "\n" + stderr)
        if stderr != "":
            raise ActionError({'error':"Failed to parse model list:\n" + stderr})
        model_list = []
        lines = [line for line in model_list_txt.split("\n") if line != ""]
        for line in lines:
            tokens = line.split(":")
            self.debug("tokens="+str(tokens))
            if tokens[0] == 'netconf':
                model_list += [tokens[1]]
            else:
                model_list += [tokens[0]]
        return model_list

class GetOp(NetconfOp):
    def _init_params(self, params):
        self.subtree = self.param_default(params, ns.ns.pioneer_subtree, "")
        self.xpath = self.param_default(params, ns.ns.pioneer_xpath, "")

    def perform(self):
        self.debug("netconf_get() with device {0}".format(self.dev_name))
        self.extend_timeout(90) # Max 90 seconds for get, ok?
        reply = self.nc_perform(subtree=self.subtree, xpath=self.xpath)
        return {'get-reply':reply}

class GetConfigOp(NetconfOp):
    def _init_params(self, params):
        self.subtree = self.param_default(params, ns.ns.pioneer_subtree, "")
        self.xpath = self.param_default(params, ns.ns.pioneer_xpath, "")

    def perform(self):
        self.debug("netconf_get_config() with device {0}".format(self.dev_name))
        self.extend_timeout(90) # Max 90 seconds for get, ok?
        reply = self.nc_perform(op='get-config', subtree=self.subtree, xpath=self.xpath)
        return {'get-config-reply':reply}

class HelloOp(NetconfOp):
    def perform(self):
        self.debug("netconf_hello() with device {0}".format(self.dev_name))
        self.extend_timeout(180) # Max 180 seconds for hello, ok?
        hello = self.nc_perform(op='hello')
        return {'hello-reply':hello}
