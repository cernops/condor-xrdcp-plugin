#!/usr/bin/env python3

import sys
import os
import re
import time
import getpass
from subprocess import Popen, PIPE

import classad

XRDCP_VERSION = '1.0.0'
XROOTD_URI_REGEX = re.compile(r'^(?P<server>root://[^/]+)/(?P<path>/.*)$')
MAX_ERR_LEN = 1024


def print_help(stream = sys.stderr):
    help_msg = '''Usage: {0} -infile <input-filename> -outfile <output-filename>
       {0} -classad
Options:
  -classad                    Print a ClassAd containing the capablities of this
                              file transfer plugin.
  -infile <input-filename>    Input ClassAd file
  -outfile <output-filename>  Output ClassAd file
  -upload                     Indicates this transfer is an upload (default is
                              download)
'''
    stream.write(help_msg.format(sys.argv[0]))


def print_capabilities():
    capabilities = {
        'MultipleFileSupport': True,
        'PluginType': 'FileTransfer',
        'SupportedMethods': 'root',
        'Version': XRDCP_VERSION,
    }
    sys.stdout.write(classad.ClassAd(capabilities).printOld())


def parse_args():

    # The only argument lists that are acceptable are
    # <this> -classad
    # <this> -infile <input-filename> -outfile <output-filename>
    # <this> -outfile <output-filename> -infile <input-filename>
    if not len(sys.argv) in [2, 5, 6]:
        print_help()
        sys.exit(1)

    # If -classad, print the capabilities of the plugin and exit early
    if (len(sys.argv) == 2) and (sys.argv[1] == '-classad'):
        print_capabilities()
        sys.exit(0)

    # If -upload, set is_upload to True and remove it from the args list
    is_upload = False
    if '-upload' in sys.argv[1:]:
        is_upload = True
        sys.argv.remove('-upload')

    # -infile and -outfile must be in the first and third position
    if not (
            ('-infile' in sys.argv[1:]) and
            ('-outfile' in sys.argv[1:]) and
            (sys.argv[1] in ['-infile', '-outfile']) and
            (sys.argv[3] in ['-infile', '-outfile']) and
            (len(sys.argv) == 5)):
        print_help()
        sys.exit(1)
    infile = None
    outfile = None
    try:
        for i, arg in enumerate(sys.argv):
            if i == 0:
                continue
            elif arg == '-infile':
                infile = sys.argv[i+1]
            elif arg == '-outfile':
                outfile = sys.argv[i+1]
    except IndexError:
        print_help()
        sys.exit(1)

    return {'infile': infile, 'outfile': outfile, 'upload': is_upload}


def format_error(error):
    s = str(error)
    if len(s) > MAX_ERR_LEN:
        s = s[:MAX_ERR_LEN] + '...'
    return '{0}: {1}'.format(type(error).__name__, s)


def get_error_dict(error, url = ''):
    error_string = format_error(error)
    error_dict = {
        'TransferSuccess': False,
        'TransferError': error_string,
        'TransferUrl': url,
    }

    return error_dict


class XRDCPPlugin(object):

    def __init__(self):
        self.tgt_name = None
        self.meta = {}
        self._checked_paths = []

    def get_tgt_name(self, username):
        return os.path.join(os.getcwd(), f"{username}.cc")

    def ensure_dirs(self, server, dirpath):
        """
        Ensure that the directory structure for the given directory on the given server exists
        """
        if dirpath in self._checked_paths:
            return True
        if self.check_path(server, dirpath):
            return True
        rtn, out, err = self._exec_xrdfs(server, dirpath, 'mkdir', ['-p'])
        if rtn != 0:
            error_message = 'Error: {0}\nOutput: {1}'.format(err, out)
            raise RuntimeError(error_message)
        self._checked_paths.append(dirpath)
        return True

    def list_files(self, server, dirpath):
        """
        List the files in the given directory on the given server
        """
        rtn, out, err = self._exec_xrdfs(server, dirpath, 'ls')
        if rtn != 0:
            error_message = 'Error: {0}\nOutput: {1}'.format(err, out)
            raise RuntimeError(error_message)
        return out

    def check_path(self, server, path):
        rtn, _, _ = self._exec_xrdfs(server, path, 'stat')
        if rtn != 0:
            self._checked_paths.append(path)
            return True
        return False

    def _exec_xrdfs(self, server, path, operation, options=[]):
        env = os.environ.copy()
        env["XRD_APPNAME"] = "condor_xrdcp_plugin"
        if self.tgt_name:
            env["KRB5CCNAME"] = f"FILE:{self.tgt_name}"
        cmd = ['xrdfs', server, operation] + options + [path]
        child_p = Popen(cmd, stdout=PIPE, stderr=PIPE, env=env)
        child_out, child_err = child_p.communicate()
        return child_p.returncode, child_out, child_err

    def _exec_xrdcp(self, src, dest):
        env = os.environ.copy()
        env["XRD_APPNAME"] = "condor_xrdcp_plugin"
        if self.tgt_name:
            env["KRB5CCNAME"] = f"FILE:{self.tgt_name}"
        xrdcp_cmd = ["xrdcp", "--nopbar", "--debug", ""
                                                     "1", "-f"]

        # we need to write even if the target exists:
        if src.endswith("/") or src.endswith("."):
            # I guess we are transferring a directory
            xrdcp_cmd.append("-r")
        xrdcp_cmd.extend([src, dest])

        child_p = Popen(xrdcp_cmd, stdout=PIPE, stderr=PIPE, env=env)
        child_out, child_err = child_p.communicate()
        if child_p.returncode != 0:
            raise RuntimeError(child_err)
        else:
            return child_out

    def parse_url(self, url):
        """
        Parse the URL and return a tuple with the server and path
        Note server is returned with the protocol maintained, ie root://eosuser.cern.ch
        """
        match = XROOTD_URI_REGEX.match(url)
        if match:
            return match.group('server'), match.group('path')
        else:
            raise ValueError

    def unparse_url(self, server, path):
        """
        Unparse the URL from the server and path

        """
        return f"{server}/{path}"

    def download_file(self, url, local_file_path):

        start_time = time.time()

        # presume we don't care about output, but perhaps useful at some point for debugging
        _ = self._exec_xrdcp(src=url, dest=local_file_path)
        file_size = os.path.getsize(local_file_path)

        end_time = time.time()

        # Get transfer statistics
        transfer_stats = {
            'TransferSuccess': True,
            'TransferProtocol': 'xrootd',
            'TransferType': 'download',
            'TransferFileName': local_file_path,
            'TransferFileBytes': file_size,
            'TransferTotalBytes': file_size,
            'TransferStartTime': int(start_time),
            'TransferEndTime': int(end_time),
            'ConnectionTimeSeconds': int(end_time - start_time),
            'TransferUrl': url,
        }

        return transfer_stats

    def upload_file(self, url, local_file_path):

        start_time = time.time()
        server, upload_path = self.parse_url(url)
        upload_file = os.path.basename(upload_path)
        upload_dir = os.path.dirname(upload_path)
        if upload_file == "_condor_stdout" and "Out" in self.meta:
            upload_file = self.meta["Out"]
        if upload_file == "_condor_stderr" and "Err" in self.meta:
            upload_file = self.meta["Err"]
        upload_path = os.path.join(upload_dir, upload_file)
        url = self.unparse_url(server, upload_path)
        if "XRDCP_CREATE_DIRS" in self.meta and self.meta["XRDCP_CREATE_DIRS"]:
            self.ensure_dirs(server, upload_dir)

        _ = self._exec_xrdcp(src=local_file_path, dest=url)
        file_size = os.path.getsize(local_file_path)

        end_time = time.time()

        transfer_stats = {
            'TransferSuccess': True,
            'TransferProtocol': 'xrootd',
            'TransferType': 'upload',
            'TransferFileName': local_file_path,
            'TransferFileBytes': file_size,
            'TransferTotalBytes': file_size,
            'TransferStartTime': int(start_time),
            'TransferEndTime': int(end_time),
            'ConnectionTimeSeconds': int(end_time - start_time),
            'TransferUrl': url,
        }

        return transfer_stats


def main():

    try:
        args = parse_args()
    except Exception:
        sys.exit(1)

    xrdcp_plugin = XRDCPPlugin()

    job_ads = []
    machine_ads = []
    try:
        job_ads = classad.parseAds(open(".job.ad", "r"))
    except Exception:
        # is this the right thing to do?
        # If the plugin is somehow running on the schedd (and whilst it shouldn't, it can!),
        # then there won't be a .job.ad file
        pass

    try:
        machine_ads = classad.parseAds(open(".machine.ad", "r"))
    except Exception:
        pass

    job_ad = None
    machine_ad = None
    plugin_meta = {}

    for j in job_ads:
        job_ad = j
        break

    for m in machine_ads:
        machine_ad = m
        break

    if job_ad:
        plugin_meta["Owner"] = job_ad["Owner"]
        if "SubmittedOut" in job_ad:
            plugin_meta["Out"] = job_ad["SubmittedOut"]
        if "SubmittedErr" in job_ad:
            plugin_meta["Err"] = job_ad["SubmittedErr"]
        if "XRDCP_CREATE_DIR" in job_ad:
            plugin_meta["XRDCP_CREATE_DIR"] = job_ad["XRDCP_CREATE_DIR"]
            # FIXME we should do something better for truthiness of this value

    if machine_ad:
        if "OpSysAndVer" in machine_ad:
            plugin_meta["OpSysAndVer"] = machine_ad["OpSysAndVer"]

    xrdcp_plugin.meta = plugin_meta

    try:
        infile_ads = classad.parseAds(open(args['infile'], 'r'))
    except Exception as e:
        try:
            with open(args['outfile'], 'w') as outfile:
                outfile_dict = get_error_dict(e)
                outfile.write(str(classad.ClassAd(outfile_dict)))
        except Exception:
            pass
        sys.exit(1)

    # we will need the running user to get the correct credentials
    if "Owner" in plugin_meta:
        running_user = plugin_meta["Owner"]
    else:
        running_user = getpass.getuser()

    # Iterate over the classads and perform transfers
    # Potential TODO: xrdcp can copy multiple files
    try:
        with open(args['outfile'], 'w') as outfile:
            for ad in infile_ads:
                xrdcp_plugin.tgt_name = xrdcp_plugin.get_tgt_name(running_user)
                try:
                    if not args['upload']:
                        outfile_dict = xrdcp_plugin.download_file(ad['Url'], ad['LocalFileName'])
                    else:
                        outfile_dict = xrdcp_plugin.upload_file(ad['Url'], ad['LocalFileName'])

                    outfile.write(str(classad.ClassAd(outfile_dict)))

                except Exception as e:
                    try:
                        outfile_dict = get_error_dict(e, url=ad['Url'])
                        outfile.write(str(classad.ClassAd(outfile_dict)))
                    except Exception:
                        pass
                    sys.exit(1)

    except Exception:
        sys.exit(1)


if __name__ == '__main__':
    # All failures should result in error code -1.
    # This is true even if we cannot write a Classad to the outfile.
    #
    # Exiting -1 without an outfile thus means one of two things:
    # 1. Could not parse arguments
    # 2. Could not open outfile for writing.
    main()
