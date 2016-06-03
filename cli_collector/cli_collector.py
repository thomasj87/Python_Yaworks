#!/usr/bin/env python -tt
"""
Script that allows you to collect data from network via CLI.
There is an option to collect data via Jumpserver.
"""

import argparse
import logging
import os
import platform
import sys

from lib import ConnectionManager, HostManager, accountmgr, utils

__author__ = "Thomas Jongerius"
__copyright__ = "Copyright 2016, Thomas Jongerius"
__credits__ = ["Thomas Jongerius", "Alan Holt"]
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Thomas Jongerius"
__email__ = "thomasjongerius@yaworks.nl"
__status__ = "Development"


def option_parser():
    """Option parser allows command line options to be parsed.
    Requires the argparse module."""

    parser = argparse.ArgumentParser(
        description='''Script that allows you to collect data from network via CLI.''',
        epilog='Created by ' + __author__ + ', version ' + __version__ + ' ' + __copyright__)
    parser.add_argument("--reset", "-r", help="Option will reset all key ring password and ask for password always.",
                        dest='reset', action='store_true')
    parser.add_argument("--debug", "-d", metavar='LEVEL', type=str, default="CRITICAL", dest='debug',
                        help='''
                        Prints out debug information about the device connection stage.
                        LEVEL is a string of DEBUG, INFO, WARNING, ERROR, CRITICAL.
                        Default is CRITICAL.
                        ''')
    parser.add_argument("-o", "--output_dir", help="Output directory for export command output",
                        type=str, default=None, dest='output_dir')
    parser.add_argument("-j", "--json_output", help="Output JSON file",
                        type=str, default=None, dest='output_json')
    parser.add_argument("-c", "--connection", help="Connection Type (Default: SSH)",
                        type=str, default='SSH', dest='connection', choices=['SSH', 'TELNET'])

    parser.add_argument('setting_file', help="File containing connection settings",
                        type=str, metavar='SETTINGS_FILE')
    parser.add_argument('device_list', metavar='DEVICE_LIST', type=str,
                        help="Text file with list of devices to collect data from.")
    parser.add_argument('command_list', metavar='COMMAND_LIST', type=str,
                        help="Text file with list of commands to collect.")
    parser.add_argument('credentials', help="File containing credentials and/or references",
                        type=str, metavar='CREDENTIAL_FILE')

    return parser.parse_args()


def main():
    args = option_parser()

    logging.debug("Started")

    logging.info("Level of debugging: {}".format(args.debug))
    logging.info("System running: {} ({})".format(platform.system(), os.name))
    logging.info("Output directory: {}".format(args.output_dir))
    logging.info("JSON output file: {}".format(args.output_json))
    logging.info("Credential file: {}".format(args.credentials))
    logging.info("Credential reset: {}".format(args.reset))
    logging.info("Settings file: {}".format(args.setting_file))
    logging.info("Device list file: {}".format(args.device_list))
    logging.info("Command list file: {}".format(args.command_list))

    # Open files that are required.
    try:
        with open(args.device_list) as device_file:
            hosts_list = device_file.read().splitlines()
        with open(args.command_list) as device_file:
            commands_list = device_file.read().splitlines()
    except IOError as e:
        logging.error("I/O error({0}): {1}".format(e.errno, e.strerror))
        sys.exit(10)

    s = utils.read_from_json_file(args.setting_file)

    # Create list with jumpservers as Device objects
    jumpservers = []

    if 'PATH' in s['SETTINGS']:
        if len(s['SETTINGS']['PATH']) > 0:
            for j in s['SETTINGS']['PATH']:
                if j in s['JUMPSERVERS']:
                    jumpservers.append(HostManager.Device(j,
                                                          prompt=s['JUMPSERVERS'][j]['PROMPT'],
                                                          ssh=s['JUMPSERVERS'][j]['SSH_COMMAND'],
                                                          telnet=s['JUMPSERVERS'][j]['TELNET_COMMAND'],
                                                          connection_type=s['JUMPSERVERS'][j]['CONNECTION_TYPE'],
                                                          timeout=s['JUMPSERVERS'][j]['TIMEOUT'],
                                                          port=s['JUMPSERVERS'][j]['PORT']))
                else:
                    logging.critical("Jumpserver {} could not be found in settings!".format(j))

    # Setting up connection and output collector objects
    d = ConnectionManager.ConnectionAgent(am=accountmgr.AccountManager(
                                              config_file=args.credentials, reset=args.reset),
                                          client_connection_type=args.connection,
                                          ssh_command=s['SETTINGS']['SSH_COMMAND'],
                                          telnet_command=s['SETTINGS']['TELNET_COMMAND'],
                                          timeout=s['SETTINGS']['TIMEOUT'],
                                          shell=s['SETTINGS']['SHELL'],
                                          jumpservers=jumpservers)
    h = HostManager.HostManagment()


    # Walk through list of hosts, connect, execute command and save to object.
    for host in hosts_list:
        h.add_host(host)
        d.host_connect(host)
        d.cisco_term_len()
        for command in commands_list:
            h.add_command(host, command, d.send_command(command))
        d.disconnect_host()

    # Saving output if neeeded.
    if args.output_dir:
        utils.dir_check(args.output_dir)
        h.write_to_txt_files(args.output_dir)
    if args.output_json:
        h.write_to_json(args.output_json)

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
