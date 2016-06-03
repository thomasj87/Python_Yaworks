#!/usr/bin/env python -tt
"""Script that allows you to collect data from network via CLI.
There is an option to collect data via Jumpserver.

Feature wish list: Stacking jumpservers.
"""

import logging
import datetime
from utils import write_dict_to_json_file

__author__ = "Thomas Jongerius"
__copyright__ = "Copyright 2016, Thomas Jongerius"
__credits__ = ["Thomas Jongerius", "Alan Holt"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Thomas Jongerius"
__email__ = "thomasjongerius@yaworks.nl"
__status__ = "Development"


class Device(object):
    '''
    Device object containing device settings.
    '''

    def __init__(self, name,
                 ipv4=None, username=None,
                 password=None, port=None,
                 prompt=None, timeout=10,
                 ssh=None, telnet=None,
                 connection_type='SSH'):

        self.name = name
        self.ipv4 = ipv4

        self.connection_settings = {
            "USERNAME": username,
            "PASSWORD": password,
            "PROMPT": prompt,
            "SSH_COMMAND": ssh,
            "TELNET_COMMAND": telnet,
            "CONNECTION_PORT": port,
            "TIMEOUT": timeout,
            "CONNECTION_TYPE": connection_type
        }

class HostManagment(Device):
    '''
    Host Manager to keep data for hosts. Export, and import data.
    '''

    def __init__(self, prefix=None, postfix='.log'):
        super(Device, self).__init__()

        self.hm = {}
        self.prefix = prefix
        self.postfix = postfix

    def add_host(self, host, **kwargs):
        self.hm[host] = {}

        d = Device(host)

        if kwargs:
            if 'ipv4' in kwargs:
                d.ipv4 = kwargs['ipv4']
            if 'prompt' in kwargs:
                d.connection_settings['PROMPT'] = kwargs['prompt']
            if 'timeout' in kwargs:
                d.connection_settings['TIMEOUT'] = kwargs['timeout']

        self.hm[host]['SETTINGS'] = d

    def add_command(self, host, command, output=None):
        '''
        Function to add command to host and timestamp of output retrieval.
        '''
        if host not in self.hm:
            self.add_host(host)

        self.hm[host][command] = {'OUTPUT': output,
                                  'TIMESTAMP': str(datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))}

    def write_to_json(self, filename):
        logging.debug("Writing JSON output to {}...".format(filename))
        write_dict_to_json_file(filename, self.hm, indent=2)

    def write_to_txt_files(self, output_dir):
        logging.debug("Writing files to {}...".format(output_dir))
        for host in self.hm:
            logging.debug("Writing files for {}...".format(host))
            for command in self.hm[host]:
                logging.debug("Command: {}".format(command))
                self.create_file(host=host, command=command,
                                 output=self.hm[host][command]['OUTPUT'],
                                 output_dir=output_dir)

    def create_file(self, host, output, output_dir, sep='_', command=None, timestamp=None):
        '''
        Function to create files in desired output directory with options.
        '''

        # Setting up path
        s = sep
        filename = output_dir + host

        if command:
            command = command.replace(' ', '_')
            filename = filename + s + command

        if timestamp:
            filename = filename + s + timestamp

        if self.postfix:
            filename = filename + self.postfix

        # Write to file
        target = open(filename, 'w')
        target.writelines(output)
        target.close()
