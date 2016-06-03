#!/usr/bin/env python -tt
"""
Connection Manager library for managing connections to hosts.
"""

import logging
import sys
import pexpect
import time
import accountmgr
import re

__author__ = "Thomas Jongerius"
__copyright__ = "Copyright 2016, Thomas Jongerius"
__credits__ = ["Thomas Jongerius", "Alan Holt"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Thomas Jongerius"
__email__ = "thomasjongerius@yaworks.nl"
__status__ = "Development"


class ConnectionHandler(object):
    """
    ConnectionHandler for universal connection responses for pExpect in this module.
    """

    def __init__(self):

        self.handlers = [pexpect.TIMEOUT, pexpect.EOF,
                         '[U|u]sername: ',
                         '[P|p]assword: ',
                         '\w+#',
                         '\w+>',
                         'Permission denied',
                         '.*Connection refused.*',
                         '.*Offending RSA key.*']

    def get_handlers(self, added_value=None):
        # type: (str) -> lst
        """
        Function to return handler and allow user to add first handler.

        Args:
            added_value: String that can be used as re.compile

        Returns:
            list: List of re.compile strings.
        """
        return_value = [added_value]

        for v in self.handlers:
            return_value.append(v)

        return return_value


# noinspection PyArgumentList,PyCallByClass,PyTypeChecker,PyUnresolvedReferences
class ConnectionAgent(object):
    """
    Connection Agent to manage connection to the hosts.
    May invoke JumphostAgent to connect to multiple jumphosts
    """

    def __init__(self, am=accountmgr.AccountManager,
                 client_connection_type='SSH',
                 ssh_command='ssh USER@HOST -p PORT',
                 telnet_command='telnet HOST:PORT',
                 timeout=10,
                 shell='/bin/bash',
                 jumpservers=None,
                 max_retry=5):
        """
        Connection Manager for managing connections. (Via Jumpnode)

        Args:
            am: Account Manager Object to obtain security credentials securely. (obj)
            client_connection_type: Connection type [SSH || TELNET] (str)
            ssh_command: Variable for current SSH command (str)
            telnet_command: Variable for current Telnet command (str)
            timeout: Variable for current timeout value (int)
            shell: Shell command (future use) (str)
            jumpservers: List of Device objects (lst: -> obj)
            max_retry: Maximum retry attempts for connections (int)

        Returns:
            object: Connection Object for maintaining connection to hosts.
        """

        self.prompt = pexpect.spawn  # PEXPECT Class definition for prompt.
        self.ch = ConnectionHandler()  # Connection handler object (obj)
        self.am = am

        # Connection settings
        self.ssh_command = ssh_command
        self.telnet_command = telnet_command
        self.timeout = timeout
        self.max_retry = max_retry
        self.jumpservers = jumpservers
        self.conn_type = client_connection_type
        # TODO
        self.initial_values = {'CONNECTION_TYPE': client_connection_type,
                               'SSH_COMMAND': ssh_command,
                               'TELNET_COMMAND': telnet_command,
                               'TIMEOUT': timeout}  # Initial settings for fallback

        # Prompt settings
        self.current_prompt = None  # Current prompt (str)
        self.fallback_prompt = None  # Current fallback prompt (Last Jumpserver) (str)
        self.fallback_jumpserver_name = 'localhost'  # Current fallback prompt (Last Jumpserver) (str)
        self.current_connected_host = 'localhost'  # Name of host currently connected to (str)

        # TODO
        self.shell = shell

        # TODO Initial setup without jumpserver support
        if len(self.jumpservers) > 0:
            self.connect_jumpserver(self.jumpservers)
        else:
            logging.error("For now connection can only be build through a jumpserver.")
            logging.error("Direct connection feature will be build in the near future.")
            logging.error("Script will exit now.")
            sys.exit(101)

    @staticmethod
    def get_status():
        """
        Function to return status code. Documentation purposes.
        """

        status_pool = {100: 'SUCCESSFUL',
                       101: 'PRIV_MODE',
                       102: 'ENABLE_MODE',
                       103: 'CONFIG_MODE',
                       150: 'USERNAME_PROMPT_DETECTED',
                       151: 'PASSWORD_PROMPT_DETECTED',
                       200: 'FAILED',
                       201: 'FALLBACK',
                       202: 'AUTHENTICATION_ISSUE',
                       300: 'UNKNOWN'}

        return status_pool

    def _jumpconnect_check(self, host):
        """
        Function to check if hostname or ip is part of jumpserver list.

        Args:
            host (str): hostname or ip
        """
        for j in self.jumpservers:
            if host == j.name:
                return True

        return False

    @staticmethod
    def _special_escape(string):
        """
        Function to fix special characters.

        Args:
            string (str): sting for fix
        """
        special_lst = ["$"]
        return_string = []

        for x in string:
            if x in special_lst:
                return_string.append(u'\\\\')
            return_string.append(x)

        return ''.join(return_string)

    def host_connect(self, host, connection_type=None,
                     timeout=None, expected_prompt=None,
                     port=None):
        """
        Function to connect to host. And return status.

        host :: string for hostname or IP
        """

        # Set values if given or use initial value.
        if connection_type is None:
            connection_type = self.conn_type
        if timeout is None:
            timeout = self.timeout
        if expected_prompt is None:
            expected_prompt = str(host) + "#"

        # Setting up connection per type selected.
        if connection_type == 'SSH':
            # Port settings, fallback to default if not set.
            if port is None:
                port = 22

            status = self.ssh_connection(host, timeout=timeout,
                                         expected_prompt=expected_prompt,
                                         port=port)
        elif connection_type == 'TELNET':
            # Port settings, fallback to default if not set.
            if port is None:
                port = 23

            status = self.telnet_connection(host, timeout=timeout,
                                            expected_prompt=expected_prompt,
                                            port=port)
        # No other connection type yet.
        else:
            logging.error("Other connection types not yet supported ({})!".format(connection_type))
            sys.exit(101)

        # Detecting and validating prompt if connected
        if status == 100:
            status = self.prompt_detect(host, expected_prompt=expected_prompt)

        # Acting on connection status
        # When not correctly connected. Try to fallback if connected to jumpserver.
        # Except when trying to connect to jumpserver
        # TODO Fix
        #  if status != 100|101 and len(self.jumpservers) > 0 \
        #         and self._jumpconnect_check(host) is False:
        if status >= 102:
            logging.error('Could not detect prompt for {}. Trying to fall back! Status: {}'.format(host, status))
            status = self.disconnect_host

        if status == 100:
            logging.debug('Successfully connected to {}!'.format(host))
            self.current_connected_host = host
        elif status == 101:
            logging.warn('Successfully connected to {} (priv mode)!'.format(host))
            self.current_connected_host = host
        elif status == 200:
            logging.error('Could not connect to {}!'.format(host))
        else:
            logging.critical('Unknown error for {}!'.format(host))
            status = 300

        return status

    def cisco_term_len(self):
        """
        Function to set terminal length for Cisco devices.
        """

        term = 'terminal length 0'

        logging.debug("Sending '{}' for extending terminal output...".format(term))
        self.prompt.sendline(term)

        response = self.prompt.expect([self.current_prompt, pexpect.TIMEOUT], timeout=self.timeout)

        if response == 0:
            pass
        else:
            logging.critical("Unknown response!")
            self.disconnect_host()
            sys.exit(200)

    def send_command(self, command, allow_more_show=False):
        """
        Function to send command. Validation for 'show'-commands prior to execution.

        :param allow_more_show:  Validation for 'show'-commands only. (bool)
        :param command: Command for execution (str)
        :return: Return response on return of current prompt.
        """

        search_show = re.search(r'show\s\w*', command)

        if allow_more_show or search_show:

            self.prompt.sendline(command)

            response = self.prompt.expect([self.current_prompt, pexpect.TIMEOUT], timeout=self.timeout)

            if response == 0:
                logging.info("Command {} executed!".format(command))
                return self.prompt.before
            else:
                logging.critical("Unknown response!")
                self.disconnect_host()
                sys.exit(200)
        else:
            logging.warn("Command \"{}\" has not been executed! "
                         "This is no \"show\"-command. "
                         "Make sure you execute fully typed show commands.".format(command))

    # noinspection PyUnusedLocal
    def disconnect_host(self):
        """
        Function to fallback to original prompt or disconnect self.prompt
        """

        back_to_prompt = False
        count = 1
        max_count = 3
        timeout = 3

        # Logging only
        if self.current_connected_host is None:
            logging.error('Nothing to disconnect from!')
        else:
            logging.debug('Trying to disconnect from {}...'.format(self.current_connected_host))

        # Validate if fallback prompt is set.
        if self.fallback_prompt is None:
            logging.error('Do not know what prompt to fall back to!')
            raise
        else:
            logging.debug('Falling back to prompt: {}'.format(self.fallback_prompt))

        # Send clear line and exit signal
        self.prompt.sendline()
        self.prompt.sendline('exit')

        # Continue to try and fallback.
        while back_to_prompt is False:
            logging.debug('Trying to fall back ({} out of {})...'.format(count, max_count))

            time.sleep(1)
            response = self.prompt.expect([self.fallback_prompt, pexpect.TIMEOUT], timeout=timeout)

            if response == 0:
                logging.debug('Disconnected from {}!'.format(self.current_connected_host))
                back_to_prompt = True
                self.current_connected_host = None
                status = 100
            elif response == 1:
                self.prompt.sendline()
                self.prompt.sendline('exit')
            else:
                logging.critical("Unknown error!")
                raise

            count += 1

            if count > max_count:
                logging.critical('Could not fall back to {}'.format(self.fallback_prompt))
                status = 200

    # noinspection PyUnusedLocal
    def password_handler(self, host, user,
                         expected_prompt=None,
                         password=None, password_type='Fixed',
                         timeout=None, max_retry_count=5,
                         ad=False):
        """
        Password prompt handler.

        Returns:
            bool: Connection status.
        """

        # Connection handler list
        connection_handler = self.ch.get_handlers(expected_prompt)

        # Setup variables
        prompt_detected = False
        retry_count = 0
        status = 0

        if password is None:
            password = self.am.get_password(host, username=user)
        if timeout is None:
            timeout = self.timeout

        # If password is already detected, send password directly.
        if ad:
            logging.debug("Function called with prompt already detected. Sending password...")
            self.prompt.sendline(password)

        # Loop until prompt detection.
        while not prompt_detected and retry_count <= max_retry_count:

            time.sleep(1)
            response = self.prompt.expect(connection_handler, timeout=timeout)

            if not prompt_detected and retry_count > 0:
                logging.debug("Password detection for {} ({} out of {})...".format(host, retry_count,
                                                                                   max_retry_count))

            if response == 0:
                logging.debug("Seems prompt has returned! (Expected)")
                prompt_detected = True
                status = 100
            elif response == 1:
                logging.error("Connection timed out! Reading current buffer...")
                logging.error("Dumping due to development...")
                logging.error(self.prompt)
                status = 300
            elif response == 3:
                logging.warn("Seems like falling back to username. Re-entry username!")
                self.user_handler(host, user=user, expected_prompt=expected_prompt,
                                  timeout=timeout, ad=True)
                status = 150
            elif response == 4:
                logging.debug("Password line detected!")
                logging.debug("Sending password...")
                self.prompt.sendline(password)
                status = 151
            elif response == 5 or response == 6:
                logging.info("Seems prompt has returned! (Not expected)")
                prompt_detected = True
                status = 100
            elif response == 7:
                logging.error("Authentication issue for {}".format(host))
                password = self.am.get_password(host, username=user, reset=True)
                status = 202
            elif response == 8:
                logging.error("Connection issues, cannot connect!")
                prompt_detected = True
                status = 200
            elif response == 9:
                logging.error("Connection issues, cannot connect!")
                logging.error("RSA Key seems not matching, "
                              "make sure the correct key is on {} for {}!".
                              format(self.fallback_jumpserver_name, host))
                prompt_detected = True
                status = 202
            else:
                raise

            retry_count += 1

        return status

    def user_handler(self, host, user=None,
                     expected_prompt=None,
                     timeout=None, max_retry_count=5, ad=False):
        """
        User prompt handler.
        """

        # Connection handler list
        if expected_prompt is None:
            expected_prompt = '\w+[#|>]'

        connection_handler = self.ch.get_handlers(expected_prompt)

        # Setup variables
        prompt_detected = False
        retry_count = 0
        status = 0

        if user is None:
            user = self.am.get_username(host)
        if timeout is None:
            timeout = self.timeout

        # If username prompt is already detected, send username directly.
        if ad:
            logging.debug("Function called with prompt already detected. Sending username...")
            self.prompt.sendline(user)

        # Loop until prompt detection.
        while not prompt_detected and retry_count <= max_retry_count:

            time.sleep(1)
            response = self.prompt.expect(connection_handler, timeout=timeout)

            if not prompt_detected and retry_count > 0:
                logging.debug("Retry for username for {}... "
                              "({} out of {})...".format(host, retry_count, max_retry_count))

            if response == 0 or response == 5 or response == 6:
                logging.warn("Seems prompt has returned and no password is required!")
                prompt_detected = True
                status = 100
            elif response == 1:
                logging.error("Connection timed out! Reading current buffer...")
                logging.error("Dumping due to development...")
                logging.error(self.prompt)
                status = 200
            elif response == 3:
                logging.debug("Username line detected!")
                logging.debug("Sending username...")
                self.prompt.sendline(user)
                status = 150
            elif response == 4:
                logging.debug("Password line detected!")
                prompt_detected = True
                status = 151
            else:
                logging.critical("Unknown response!")
                logging.error(self.prompt)
                raise

            retry_count += 1

        return status

    def prompt_detect(self, host, expected_prompt=None):
        """
        Prompt detector.
        """

        # Connection handler list
        connection_handler = self.ch.get_handlers(expected_prompt)

        detected = False
        detect_count = 1
        max_detect_count = 3
        status = 0

        logging.debug("Trying to receive prompt on {} ({})...".format(host, expected_prompt))
        self.prompt.sendline()

        while not detected and detect_count < max_detect_count:
            response = self.prompt.expect(connection_handler, timeout=self.timeout)

            if response == 0:
                logging.debug("Expected prompt received!")
                detected = True
                status = 100
            elif response == 5 and expected_prompt is not None:
                logging.debug("Enable mode prompt received!")
                detected = True
                status = 100
            elif response == 6 and expected_prompt is not None:
                logging.warn("Privilege mode prompt received!")
                detected = True
                status = 101
            elif response == 0:
                logging.debug("Action timed out, retry ({} out of {}).".format(detect_count, max_detect_count))
                self.prompt.sendline()
            else:
                logging.critical("Error!")
                raise

            detect_count += 1

        try:
            r_line = self.prompt.after.splitlines()
            actual_prompt = r_line[-1]
            logging.debug("Detected prompt '{}'!".format(actual_prompt))
            self.current_prompt = actual_prompt
        except:
            logging.critical("Could not detect prompt! "
                             "Do not know where we are!")
            raise

        return status

    def telnet_connection(self, host, timeout=10, port=23, expected_prompt=None):
        """
        Function to setup Telnet connection.
        """

        # Original command for replacement.
        s = self.telnet_command

        # Collection user credentials
        user = self.am.get_username(host)
        password = self.am.get_password(host, user)

        # Default port detection.
        if port != 23:
            logging.info("Alternative Telnet port detected ({}). Using this port.".format(port))

        # Setup connection cmd
        conn = s.replace("HOST", host)
        conn = conn.replace("PORT", str(port))
        # TODO Option parser to be added

        logging.debug("Connecting using '{}' command...".format(conn))

        # If no spawn instance exists. Create one.
        if isinstance(self.prompt, pexpect.spawn):
            self.prompt.sendline(conn)
        else:
            self.prompt = pexpect.spawn(conn, timeout=timeout)

        # User handling
        status = self.user_handler(host, user=user,
                                   expected_prompt=expected_prompt,
                                   timeout=timeout, max_retry_count=self.max_retry)

        # Password handling
        if status == 100:
            status = self.password_handler(host, user,
                                           expected_prompt=expected_prompt,
                                           password=password, timeout=timeout)
        elif status == 151:
            status = self.password_handler(host, user,
                                           expected_prompt=expected_prompt,
                                           password=password, timeout=timeout,
                                           ad=True)

        return status

    def ssh_connection(self, host, timeout=10, port=22, expected_prompt=None):
        """
        Function to setup SSH connection.
        """

        # Original command for replacement.
        s = self.ssh_command

        # Collection user credentials
        user = self.am.get_username(host)
        password = self.am.get_password(host, user)
        password_type = self.am.get_password_type(host)

        # Default port detection.
        if port != 22:
            logging.info("Alternative SSH port detected ({}). Using this port.".format(port))

        # Setup connection cmd
        cmd = s.replace("USER", user)
        cmd = cmd.replace("HOST", host)
        cmd = cmd.replace("PORT", str(port))
        # TODO Option parser to be added

        logging.debug("Connecting using '{}' command...".format(cmd))

        # If no spawn instance exists. Create one.
        if isinstance(self.prompt, pexpect.spawn):
            self.prompt.sendline(cmd)
        else:
            self.prompt = pexpect.spawn(cmd, timeout=timeout)

        status = self.password_handler(host, user,
                                       expected_prompt=expected_prompt,
                                       password=password, password_type=password_type,
                                       timeout=timeout)

        return status

    def connect_jumpserver(self, path):
        """
        Function to connection to Jumpserver Path and return pexpect with active prompt.

        Args:
            path: Pa
        """

        # Check for reoccurring jumpservers in existing path list.
        j_list = []
        for j in path:
            if j.name in j_list:
                logging.warn("Jumpserver {} more then once in jump path. "
                             "Delay in collection is expected!".format(j.name))
            j_list.append(j.name)

        current_jumpserver = self.fallback_jumpserver_name

        # Hop to current jumpserver and connect to the following
        logging.debug("Trying to connect to jumpservers!")

        for jumpserver in path:

            jumpserver_hostname = jumpserver.name

            if current_jumpserver != jumpserver_hostname:
                # Connect to jumphost
                status = self.host_connect(jumpserver_hostname,
                                           connection_type=jumpserver.connection_settings['CONNECTION_TYPE'],
                                           timeout=jumpserver.connection_settings['TIMEOUT'],
                                           port=jumpserver.connection_settings['CONNECTION_PORT'],
                                           expected_prompt=jumpserver.connection_settings['PROMPT'])

                self.ssh_command = jumpserver.connection_settings['SSH_COMMAND']
                self.telnet_command = jumpserver.connection_settings['TELNET_COMMAND']

                if status != 100:
                    logging.critical('Jumpserver connection unsuccessful! '
                                     'Connection required!')
                    sys.exit(103)
            else:
                logging.debug("Already connected to: {}".format(current_jumpserver))

            current_jumpserver = jumpserver_hostname
            self.fallback_jumpserver_name = current_jumpserver
            self.fallback_prompt = jumpserver.connection_settings['PROMPT']

        logging.debug("Connected to all jumpservers!")
