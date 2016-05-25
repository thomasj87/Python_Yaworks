#!/usr/bin/env python -tt
"""Script that allows you to collect data from network via CLI.
There is an option to collect data via Jumpserver.

Feature wish list: Stacking jumpservers.
"""

import logging
import argparse
import sys
import getpass
import os
import json
import platform
import pexpect
import time
import datetime
import types
import re

__author__ = "Thomas Jongerius"
__copyright__ = "Copyright 2016, Thomas Jongerius"
__credits__ = ["Thomas Jongerius", "Alan Holt"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Thomas Jongerius"
__email__ = "thomasjongerius@yaworks.nl"
__status__ = "Development"

class HostManagment(object):
    def __init__(self, output_dir=None, prefix=None, postfix='.log'):
        self.hm = {}
        self.out = output_dir
        self.prefix = prefix
        self.postfix = postfix

    def add_host(self, host):
        self.hm[host] = { }

    def add_command(self, host, command, output=None):
        self.hm[host][command] = { 'OUTPUT' : output,
                                    'TIMESTAMP' : str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))}

    def write_to_json(self, file):
        with open(file, 'w') as outfile:
            json.dump(self.hm, outfile,indent=2)
            outfile.close()

    def read_from_json(self, file):
        json_data = open(file).read()

        return json.loads(json_data)

    def dir_check(self, directory):
        if os.path.exists(directory):
            logging.debug('Path {} already exists.'.format(directory))
        else:
            logging.warn('Path {} does not yet exist. Will be created!'.format(directory))

    def create_file(self, host=None, command=None, output=None, sep='_', command_post=True, timestamp_post=True):

        if self.out is None:
            logging.error('No output directory set.')
            raise

        s = sep
        filename = self.out + host

        if command_post:
            command = command.replace(' ', '_')
            filename = filename + s + command

        if timestamp_post:
            timestamp = str(datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
            filename = filename + s + timestamp

        filename = filename + self.postfix

        target = open(filename, 'w')

        target.writelines(output)

        target.close()

class ConnectionAgent(object):
    '''
    Conneciton Agent to manage connection to the hosts.
    May invoke JumphostAgent to connect to mutible jumphosts
    '''

    def __init__(self, setting_file, account_manager=None, client_connection_type='SSH'):

        #Setting variables
        self.prompt = pexpect #PEXPECT Class definition for prompt.
        self.am = account_manager
        self.am_fallback = {}

        self.ssh_command = setting_file['SETTINGS']['SSH_COMMAND']
        self.telnet_command = setting_file['SETTINGS']['TELNET_COMMAND']
        self.timeout = setting_file['SETTINGS']['TIMEOUT']
        self.j_path = setting_file['SETTINGS']['PATH']
        self.current_prompt = None
        self.fallback_prompt = None
        self.current_connected_host = None

        _j_set = setting_file['JUMPSERVERS']

        #Check for jump path. If set, invoke JumphostAgent
        if len(self.j_path) > 0:
            self.ja = JumphostAgent(self.prompt, _j_set, ssh=self.ssh_command,
                                    telnet=self.telnet_command, timeout=self.timeout,
                                    account_manager=self.am)
            self.prompt = self.ja.connect_jump_path(self.j_path, self.prompt)
            self.ssh_command = self.ja.get_settings('SSH')
            self.telnet_command = self.ja.get_settings('TELNET')
            self.fallback_prompt = self.ja.get_settings('CPROMPT')

        else:
            logging.error("For now connection can only be build through a jumpserver.")
            logging.error("Direct connection feature will be build in the near future.")
            logging.error("Script will exit now.")
            sys.exit(100)

        self.conn_type = client_connection_type

    def hostconnect(self, host):
        '''
        Function to connect to host.

        host :: string for hostname or IP
        '''

        user, pas, type = self.user_credentials(host)

        if self.conn_type == 'SSH':
            logging.error("Building in progres... Not executing now!")
        elif self.conn_type == 'TELNET':
            self.prompt = self.telnet_connection(host, user, pas, self.telnet_command)

        logging.debug("Detecting prompt...")
        try:
            r_line = self.prompt.after.splitlines()
            if r_line:
                self.current_prompt = r_line[1]

            logging.debug("Detected prompt '{}'!".format(self.current_prompt))
            self.current_connected_host = host
            logging.debug('Connected to {}!'.format(host))

        except:
            logging.error('Could not detect prompt for {}. Trying to fall back!')
            self.hostdisconnect()

    def cisco_term_len(self):

        t = 3
        term = 'term len 0'

        self.prompt.sendline(term)

        response = self.prompt.expect(self.current_prompt, timeout=t)

        if response <= 1:
            pass
        else:
            logging.critical("Unknown response!")
            self.hostdisconnect()
            sys.exit(10)



    def telnet_prompt_connect(self, host, telnet_command, username, password=None, port=23):
        t = 10
        conn = telnet_command
        conn = conn.replace("HOST", host)
        conn = conn.replace("PORT", str(port))

        self.prompt.sendline(conn)
        user_ex_list = ['[u|U]sername:']
        pass_ex_list = ['[p|P]assword:']
        prompt_ex_list = ['#', '>']

        logging.debug("Pending for {}".format(user_ex_list))

        response = self.prompt.expect(user_ex_list, timeout=t)

        if response == 0:
            self.prompt.sendline(username)
        else:
            logging.critical("Unknown response!")
            sys.exit(10)

        response = self.prompt.expect(pass_ex_list, timeout=t)

        if response == 0:
            self.prompt.sendline(password)
        else:
            logging.critical("Unknown response!")
            sys.exit(10)

        response = self.prompt.expect(prompt_ex_list, timeout=t)

        if response == 0:
            logging.info("Priv mode!")
        elif response == 1:
            logging.info("Enable mode!")
        else:
            logging.critical("Unknown response!")
            self.hostdisconnect()
            sys.exit(10)

    def sendcommand(self, command):

        t = 10

        self.prompt.sendline(command)

        response = self.prompt.expect(self.current_prompt, timeout=t)

        if response == 0:
            logging.info("Command {} executed!".format(command))
            return self.prompt.before
        else:
            logging.critical("Unknown response!")
            self.hostdisconnect()
            sys.exit(10)


    def hostdisconnect(self):
        back_to_prompt = False
        count = 1
        max_count = 5
        t = 3

        if self.current_connected_host is None:
            logging.error('Nothing to disconnect from!')
        else:
            logging.debug('Trying to disconnect from {}...'.format(self.current_connected_host))

        if self.fallback_prompt is None:
            logging.error('Do not know what prompt to fall back to!')
            raise
        else:
            pr = self.fallback_prompt
            logging.debug('Falling back to prompt: {}'.format(self.fallback_prompt))

        while back_to_prompt is False:
            try:
                logging.debug('Trying to fall back ({} out of {})...'.format(count, max_count))
                self.prompt.expect(pr, timeout=t)
                back_to_prompt = True
            except pexpect.exceptions.TIMEOUT:
                if count <= max_count:
                    self.prompt.sendline('exit')
                    time.sleep(3)
                    count += 1
                else:
                    logging.critical('Cound not fall back to {}'.format(self.fallback_prompt))
                    raise

        logging.debug('Disconnected from {}!'.format(self.current_connected_host))
        self.current_connected_host = None

        logging.debug('Succesfully falled back to {}!'.format(self.fallback_prompt))


    def user_credentials(self, d, user=None):
        """
        Function to search for user credentials.
        """
        #TODO Pass type
        t = 'Fixed'

        if self.am is not None:
            u = self.am.get_username(d)
            p = self.am.get_password(d, u)
            t = self.am.get_password_type(d)

        return u, p, t

    def ssh_connection(self, host, user, password, pass_type, command, timeout=10, port=22, expected_prompt=None, halt_on_error=False):
        """
        Function to setup SSH connection.
        """

        #Original command for replacement.
        s = command

        #Default port detection.
        if port != 22:
            p = port
            logging.info("Alternative SSH port detected ({}). Using this port.".format(p))

        #Setup connection cmd
        conn = s.replace("USER", user)
        conn = conn.replace("HOST", host)
        conn = conn.replace("PORT", str(port))
        # TODO Option parser to be added

        logging.debug("Connecting using '{}' command...".format(conn))

        #If no spawn instanc exists. Create one.
        if isinstance(self.prompt, pexpect.spawn):
            self.prompt.sendline(conn)
        else:
            self.prompt = pexpect.spawn(conn, timeout=timeout)

        self.prompt, connected = self.password_handler(host, user, self.prompt, expected_prompt=expected_prompt)

        if connected:
            self.prompt, connected, prompt_response = self.prompt_detect(host, self.prompt, expected_prompt=expected_prompt)

        if not connected and halt_on_error:
            logging.error('Could not connect to {} while mandatory connection!'.format(host))
            raise BaseException

        return self.prompt

    def password_handler(self, host, user, prompt=pexpect, expected_prompt=None, password=None):
        """
        Password prompt handler.
        """

        # Connection handler list
        if expected_prompt is None:
            expected_prompt = '.*[#|>]'

        connection_handler = ['[P|p]assword: ',
                              'Permission denied',
                              '.*Connection refused.*',
                              expected_prompt,
                              pexpect.TIMEOUT]
        connected = False

        if password is None:
            password = self.am.get_password(host, username=user)

        detected = False
        detect_count = 0
        max_detect_count = 5

        while not detected and detect_count <= max_detect_count:

            response = prompt.expect(connection_handler, timeout=self.timeout)

            if not detected and detect_count > 0:
                logging.debug("Retry for password detection for {}... ({} out of {})...".format(host, detect_count, max_detect_count))

            if response == 0:
                    logging.debug("Password line detected!")
                    logging.debug("Sending password...")
                    self.prompt.sendline(password)
            elif response == 1:
                logging.error("Authentication issue for {}".format(host))
                password = self.am.get_password(host, username=user, reset=True)
            elif response == 2:
                logging.error("Connection issues, cannot connect!")
            elif response == 3:
                logging.debug("Seems prompt has returned!")
                detected = True
                connected = True
            elif response == 4:
                logging.error("Connection timed out! Reading current buffer...")
                logging.error("Dumping due to development...")
                logging.error(prompt)
                raise BaseException
            else:
                logging.critical("Unknown response!")
                raise BaseException

            detect_count += 1

        return prompt, connected

    def prompt_detect(self, host, prompt=pexpect, expected_prompt=None):
        """
        Prompt detector.
        """

        # Connection handler list
        connection_handler = [expected_prompt,
                              '.*#', '.*>',
                              pexpect.TIMEOUT]
        detected = False
        detect_count = 1
        max_detect_count = 3
        connected = False

        logging.debug("Trying to receive prompt on {} ({})...".format(host, expected_prompt))
        prompt.sendline()

        while not detected and detect_count < max_detect_count:
            response = prompt.expect(connection_handler, timeout=self.timeout)

            if response == 0:
                logging.debug("Expected prompt received!")
                detected = True
                connected = True
            elif response == 1 and expected_prompt is not None:
                logging.debug("Enable mode prompt received!")
                detected = True
                connected = True
            elif response == 2 and expected_prompt is not None:
                logging.debug("Privilege mode prompt received!")
                detected = True
                connected = True
            elif response == 3:
                logging.debug("Action timed out, retry ({} out of {}).".format(detect_count, max_detect_count))
                prompt.sendline()
            else:
                logging.critical("Error!")
                raise

            detect_count += 1

        try:
            r_line = prompt.after.splitlines()
            actual_prompt = r_line[-1]
            logging.debug("Detected prompt '{}'!".format(actual_prompt))

        except:
            raise

        return prompt, connected, actual_prompt

    def telnet_connection(self, host, user, password, command, timeout=10, port=23, expected_prompt=None, halt_on_error=False):
        """
        Function to setup Telnet connection.
        """

        # Original command for replacement.
        s = command

        # Default port detection.
        if port != 23:
            p = port
            logging.info("Alternative Telnet port detected ({}). Using this port.".format(p))

        # Setup connection cmd
        conn = s.replace("HOST", host)
        conn = conn.replace("PORT", str(port))
        # TODO Option parser to be added

        logging.debug("Connecting using '{}' command...".format(conn))

        # If no spawn instanc exists. Create one.
        if isinstance(self.prompt, pexpect.spawn):
            self.prompt.sendline(conn)
        else:
            self.prompt = pexpect.spawn(conn, timeout=timeout)


        # User handeling
        connection_handler = ['[u|U]sername:', 'Unknown command or computer name, or unable to find computer address.*']

        logging.debug("Pending for username line on {}...".format(host))
        response = self.prompt.expect(connection_handler, timeout=timeout)

        if response == 0:
            logging.debug("Sending username...")
            self.prompt.sendline(user)
        elif response == 1:
            logging.error("Could not connect to {}! Current buffer {}.".format(host, self.prompt.buffer))
            self.hostdisconnect()
            return self.prompt
        else:
            logging.critical("Unknown response!")
            raise

        # Password handeling
        connection_handler = ['[P|p]assword: ', 'Permission denied.*', '.*Connection refused.*']

        logging.debug("Pending for password line on {}...".format(host))
        response = self.prompt.expect(connection_handler, timeout=timeout)

        if response == 0:
            logging.debug("Sending password...")
            self.prompt.sendline(password)
        elif response == 1:
            logging.error("Authentication issue!")
            raise
        elif response == 2:
            logging.error("Connection issues, cannot connect!")
            raise
        else:
            logging.critical("Unknown response!")
            raise

        # Pending for prompt.
        if expected_prompt is None:
            expected_prompt = ['.*#', '.*>']

        logging.debug("Pending for prompt on {} ({})...".format(host, expected_prompt))
        response = self.prompt.expect(expected_prompt, timeout=timeout)

        if response == 0 or response == 1:
            logging.debug("Prompt received!")
        elif response != 0 and halt_on_error is False:
            logging.critical("No prompt received from {}. Continueing...".format(host))
        else:
            logging.critical("No prompt received! Error!")
            raise

        return self.prompt


class JumphostAgent(ConnectionAgent):
    """
    Jumper agent class, maintaining connectivity and activities from JumperHost.
    """

    def __init__(self, prompt, j_set, ssh=None, telnet=None, timeout=10, account_manager=None):

        self.prompt = prompt
        self.am = account_manager
        self.path = []
        self.original_settings = {'SSH': ssh,
                                  'TELNET': telnet,
                                  'TIMEOUT': timeout}
        self.current_jumpserver = None
        self.timeout = timeout
        self.jump_set = j_set

        #Setting SSH commands
        if ssh is None:
            ssh_def = 'ssh USER@HOST -p PORT'
            logging.warn("No SSH command set, using default: {}".format(def_ssh))
            self.ssh_command = ssh_def
        else:
            self.ssh_command = ssh

        #Setting Telnet commands
        if telnet is None:
            telnet_def = 'telnet HOST:PORT'
            logging.warn("No Telnet command set, using default: {}".format(telnet_def))
            self.telnet_command = telnet_def
        else:
            self.telnet_command = telnet


    def connect_jump_path(self, path, prompt):
        '''
        Function to connection to Jumpserver Path and return pexpect with active prompt.
        '''

        #Check if existing prompt is matching.
        logging.debug("Syncing prompt object...")
        self.prompt = prompt

        #Check for reoccuring jumpservers in existing path list.
        for p in path:
            if p in self.path:
                logging.error("Jumpserver ({}) already in path list!".format(p))
                sys.exit(100)
            else:
                self.path.append(p)

        #Hop to current jumpserver and connect to the following
        if self.current_jumpserver is None:
            logging.debug("Not yet connected to anything.")
            already_connected = False
        else:
            already_connected = True

        logging.debug("Trying to connect to jumpservers!")
        for p in self.path:
            if already_connected == False:
                self._connect_jump(p,
                                  ssh=self.ssh_command,
                                  telnet=self.telnet_command)
                self.current_jumpserver = p
            else:
                logging.debug("Already connected to: {}".format(p))

            if p == self.current_jumpserver:
                already_connected = False

        return self.prompt

    def _connect_jump(self, jump, ssh, telnet):

        username, password, pass_type = ConnectionAgent.user_credentials(self, jump)
        prompt = self.jump_set[jump]['PROMPT']
        port = self.jump_set[jump]['PORT']
        type = self.jump_set[jump]['CONNECTION_TYPE']
        timeout = self.jump_set[jump]['TIMEOUT']

        #TODO Replicate for other settings if working correctly
        try:
            timeout = self.jump_set[jump]['TIMEOUT']
        except KeyError as e:
            timeout = 10
            logging.error("Cound not find {} setting in Jumpserver setting.".format(e.message))
            logging.error("Setting default value: {}".format(timeout))
        except ValueError as e:
            timeout = 10
            logging.error("Incorrect value set for {}. Error: {}".format(e.args, e.message))
            logging.error("Setting default value: {}".format(timeout))

        logging.debug("Trying to connect to {} with {}...".format(jump, type))

        if type == "SSH":
            self.prompt = ConnectionAgent.ssh_connection(self, jump, username, password, pass_type,
                                           ssh, timeout, port, prompt, halt_on_error=True)

        elif type == "TELNET":
            self.prompt = ConnectionAgent.telnet_connection(self, jump, username, password, telnet,
                                                            timeout, port, prompt, )

        self.ssh_command = prompt = self.jump_set[jump]['SSH_COMMAND']
        self.telnet_command = prompt = self.jump_set[jump]['TELNET_COMMAND']

    def get_settings(self, setting):
        '''
        Return setting command that is requested.
        '''
        if setting == 'SSH':
            return self.ssh_command
        elif setting == 'TELNET':
            return self.telnet_command
        elif setting == 'CPROMPT':
            return self.jump_set[self.current_jumpserver]['PROMPT']
        else:
            logging.error('Unknown setting requested!')
            raise

def option_parser():
    """Option parser allows command line options to be parsed.
    Requires the argparse module."""

    parser = argparse.ArgumentParser(
        description='''Script that allows you to collect data from network via CLI.''',
        epilog='Created by ' + __author__ + ', version ' + __version__ + ' ' + __copyright__)
    parser.add_argument("--credentials", "-c", help="File containing credentials and/or references",
                        type=str, default=None, dest='cred', metavar='CREDENTIAL_FILE')
    parser.add_argument("--reset", "-r", help="Option will reset all key ring password and ask for password always.",
                        dest='reset', action='store_true')
    parser.add_argument("--debug", "-d", metavar='LEVEL', type=str, default="CRITICAL", dest='debug',
                        help='''
                        Prints out debug information about the device connection stage.
                        LEVEL is a string of DEBUG, INFO, WARNING, ERROR, CRITICAL.
                        Default is CRITICAL.
                        ''')
    parser.add_argument("--output_dir", help="Output directory for export (default: ./output/)",
                        type=str, default="./output/", dest='output_dir')

    parser.add_argument('jump', help="File containing jumphost preferences",
                        type=str, metavar='JUMPHOST_FILE')
    parser.add_argument('device_list', metavar='DEVICE_LIST', type=str,
                        help="Text file with list of devices to collect data from.")
    parser.add_argument('command_list', metavar='COMMAND_LIST', type=str,
                        help="Text file with list of commands to collect.")

    return parser.parse_args()

def main():
    args = option_parser()

    logging.debug("Started")

    logging.info("Level of debugging: {}".format(args.debug))
    logging.info("System running: {} ({})".format(platform.system(), os.name))
    logging.info("Output directory: {}".format(args.output_dir))
    logging.info("Credential file: {}".format(args.cred))
    logging.info("Credential reset: {}".format(args.reset))
    logging.info("Jumphost file: {}".format(args.jump))
    logging.info("Device list file: {}".format(args.device_list))
    logging.info("Command list file: {}".format(args.command_list))

    try:
        with open(args.device_list) as device_file:
            hosts_list = device_file.read().splitlines()
        with open(args.command_list) as device_file:
            commands_list = device_file.read().splitlines()
    except IOError as e:
        logging.error("I/O error({0}): {1}".format(e.errno, e.strerror))
        sys.exit(10)

    try:
        with open(args.jump) as jump_file:
            jumphost_dict = json.load(jump_file)
    except IOError as e:
        logging.error("I/O error({0}): {1}".format(e.errno, e.strerror))
        logging.warn("Jumpsettings not loaded!")
        jumphost_dict = None
    except ValueError as e:
        logging.error("Value error in JSON file: {}".format(e))
        logging.warn("Jumpsettings not loaded!")
        jumphost_dict = None

    if args.cred is not None:
        # try:
        import accountmgr

        am = accountmgr.AccountManager(config_file=args.cred, reset=args.reset)

        # except:
        #     logging.error("Unknown error. Account Manager error!")
        #     sys.exit(10)
    else:
        am = None
        logging.error("No credential file provided. Password must be provided in mannualy.")

    d = ConnectionAgent(jumphost_dict, account_manager=am, client_connection_type='TELNET')
    h = HostManagment(output_dir=args.output_dir)

    for host in hosts_list:
        h.add_host(host)
        d.hostconnect(host)
        d.cisco_term_len()
        for command in commands_list:
            h.add_command(host, command, d.sendcommand(command))

        d.hostdisconnect()

    h.write_to_json('output.json')
    logging.debug("Script ended")


if __name__ == '__main__':
    # Production syntax for logging
    # logging.basicConfig(stream=sys.stderr,
    #             level=logging.INFO,
    #             format="[%(levelname)8s]:%(name)s:  %(message)s")
    # Dev syntax for logging
    logging.basicConfig(stream=sys.stderr,
                        level=logging.DEBUG,
                        format="[%(levelname)8s][%(asctime)s]:%(name)s:%(funcName)s(){l.%(lineno)d}:  %(message)s")
    # TODO Create constructor!!! Remove and implement debug command

    main()
