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
import types

__author__ = "Thomas Jongerius"
__copyright__ = "Copyright 2016, Thomas Jongerius"
__credits__ = ["Thomas Jongerius", "Alan Holt"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Thomas Jongerius"
__email__ = "thomasjongerius@yaworks.nl"
__status__ = "Development"


class ConnectionAgent(object):
    '''
    Conneciton Agent to manage connection to the hosts.
    May invoke JumphostAgent to connect to mutible jumphosts
    '''


    def __init__(self, setting_file, account_manager=None, client_connection_type='SSH'):

        #Setting variables
        self.prompt = pexpect #PEXPECT Class definition for prompt.
        self.am = account_manager #TODO

        self.ssh_command = setting_file['SETTINGS']['SSH_COMMAND']
        self.telnet_command = setting_file['SETTINGS']['TELNET_COMMAND']
        self.timeout = setting_file['SETTINGS']['TIMEOUT']
        self.j_path = setting_file['SETTINGS']['PATH']

        _j_set = setting_file['JUMPSERVERS']

        #Check for jump path. If set, invoke JumphostAgent
        if len(self.j_path) > 0:
            self.ja = JumphostAgent(self.prompt, _j_set, ssh=self.ssh_command,
                                    telnet=self.telnet_command, timeout=self.timeout,
                                    account_manager=self.am)
            self.prompt = self.ja.connect_jump_path(self.j_path, self.prompt)

        else:
            print "Do nothing"
            sys.exit(10)

        self.conn_type = client_connection_type

    def hostconnect(self, host):
        # print host
        # print self.conn_type
        # print self.settings

        user = 'teopy'
        pas = 'python'

        if self.conn_type == 'SSH':
            logging.error("Building in progres... Not executing now!")
        elif self.conn_type == 'TELNET':
            self.telnet_prompt_connect(host, self.settings['TELNET_COMMAND'], user, pas)



    def cisco_term_len(self):
        t = 10
        term = 'term len 0'
        prompt_ex_list = ['#', '>']
        self.prompt.logfile = sys.stdout
        self.prompt.sendline(term)

        response = self.prompt.expect(prompt_ex_list, timeout=t)

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

        print "Going to connect to {} with {} ({}).".format(host, conn, username)
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
        prompt_ex_list = ['#', '>']
        self.prompt.logfile = sys.stdout

        response = self.prompt.expect(prompt_ex_list, timeout=t)

        if response == 0:
            logging.info("Command {} executed!".format(command))
        else:
            logging.critical("Unknown response!")
            self.hostdisconnect()
            sys.exit(10)


    def hostdisconnect(self):
        back_to_prompt = False
        count = 0
        t = 3
        pr = self.settings["PROMPT"]
        print self.settings
        print pr

        while back_to_prompt is False:
            try:
                self.prompt.expect(pr, timeout=t)
                back_to_prompt = True
            except pexpect.exceptions.TIMEOUT:
                self.prompt.sendline('exit')
                time.sleep(3)
                count += 1
                print count


    def user_credentials(self, d, user=None):
        """
        Function to search for user credentials.
        """
        #TODO Pass type
        t = 'Fixed'

        if self.am is not None:
            logging.error("No account manager function yet!")
            # TODO Merge IF

        if self.am is None:
            logging.error("No credential file provided. User credentials must be provided manually for {}.".format(d))
            if user is not None:
                u = user
            else:
                logging.error("Username not found. Please provide manually.")
                # u = getpass.getuser()
                if d == "192.168.2.101":
                    u = "teopy"
                elif d == "192.168.2.102":
                    u = "teopy"
                else:
                    u = "debian"

            logging.info("Please provide password for {}".format(u))

            # TODO password controll for testing
            if d == "192.168.2.101":
                p = "python"
            elif d == "192.168.2.102":
                p = "python"
            else:
                p = "debian"
                # p = getpass.getpass()

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

        #Connection handler list
        connection_handler = ['[P|p]assword: ', 'Permission denied.*', '.*Connection refused.*']

        #Password handeling
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

        #Pending for prompt.
        logging.debug("Pending for prompt on {} ({})...".format(host,expected_prompt))
        response = self.prompt.expect(expected_prompt, timeout=timeout)

        if response == 0:
            logging.debug("Prompt received!")
        elif response != 0 and halt_on_error is False:
            logging.critical("No prompt received from {}. Continueing...".format(host))
        else:
            logging.critical("No prompt received! Error!")
            raise

        return self.prompt

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

        connection_handler = ['[u|U]sername:']
        pass_ex_list = ['[p|P]assword:']

        # User handeling
        logging.debug("Pending for username line on {}...".format(host))
        response = self.prompt.expect(connection_handler, timeout=timeout)

        if response == 0:
            logging.debug("Sending username...")
            self.prompt.sendline(user)
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
        logging.debug("Pending for prompt on {} ({})...".format(host, expected_prompt))
        response = self.prompt.expect(expected_prompt, timeout=timeout)

        if response == 0:
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


def option_parser():
    """Option parser allows command line options to be parsed.
    Requires the argparse module."""

    parser = argparse.ArgumentParser(
        description='''Script that allows you to collect data from network via CLI.''',
        epilog='Created by ' + __author__ + ', version ' + __version__ + ' ' + __copyright__)
    parser.add_argument("--credentials", "-c", help="File containing credentials and/or references",
                        type=str, default=None, dest='cred', metavar='CREDENTIAL_FILE')
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

    if not os.path.exists(args.output_dir):
        logging.warn("Path {} does not exist. It will be created!".format(args.output_dir))
        os.mkdir(args.output_dir)

    if args.cred is not None:
        try:
            import keyring

            am = AccountManager(config_file=args.cred,
                                password_cb=prompt_for_password)

        except ImportError:
            logging.error("No keyring library installed. Password must be provided in mannualy.")
            am = None
    else:
        am = None
        logging.error("No credential file provided. Password must be provided in mannualy.")

    # TODO Only during development
    # print hosts_list
    # print commands_list
    # print jumphost_dict

    # if jumphost_dict is not None:
    #     j = JumphostAgent(jumphost_dict, account_manager=am)
    #     j.connect_jump()
    # else:
    #     j = None

    d = ConnectionAgent(jumphost_dict, account_manager=am, client_connection_type='TELNET')

    for host in hosts_list:
        d.hostconnect(host)
        d.cisco_term_len()
        for command in commands_list:
            d.sendcommand(command)
        d.hostdisconnect()

        # d.printing_var()

    # TODO For possible password asking
    # print "Test get password..."
    # password_to_use = getpass.getpass()
    # username = getpass.getuser()
    # print password_to_use
    # print username

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
