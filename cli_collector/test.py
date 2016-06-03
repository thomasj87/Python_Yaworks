class SomeBaseClass(object):
    def __init__(self, test=None):
        self.testv =  test
        print('SomeBaseClass.__init__(self) called')

    def test(self, e):
        print e

class Child(SomeBaseClass):
    def __init__(self):
        print('Child.__init__(self) called')
        SomeBaseClass.__init__(self)

class SuperChild(SomeBaseClass):
    def __init__(self):
        print('SuperChild.__init__(self) called')
        super(SuperChild, self).__init__(test='test')


s = SomeBaseClass()
child = Child()
super = SuperChild()

print s.testv
super.test('test')
print super.testv


class Device(object):
    '''
    Device object containing device settings.

    Building.....
    '''

    def __init__(self, hostname, **kwargs):

        if 'name' in kwargs:
            self.hostname = hostname
        if 'description' in kwargs:
            self.description = kwargs['description']
        if 'ip' in kwargs:
            self.ip = kwargs['ip']
        else:
            self.ip = None


        #
        #
        # "JUMPSERVERS": {
        #         "192.168.57.2": {
        #             "USERNAME": "debian",
        #             "PROMPT": "@debian:~\\$",
        #             "CONNECTION_TYPE": "SSH",
        #             "SSH_COMMAND": "ssh -o StrictHostKeyChecking=no USER@HOST -p PORT",
        #             "PORT": 22,
        #             "TELNET_COMMAND": "telnet HOST PORT",
        #             "TIMEOUT": 10
        #         },


class ConnectionAgent(object):
    """
    Connection Agent to manage connection to the hosts.
    May invoke JumphostAgent to connect to multiple jumphosts
    """

    def __init__(self, setting_file,
                 am=accountmgr.AccountManager,
                 client_connection_type='SSH',
                 ssh_command='ssh USER@HOST -p PORT',
                 telnet_command='telnet HOST:PORT',
                 timeout=10,
                 shell='/bin/bash',
                 jumpservers=None):
        ''''''
        # Setting variables
        self.prompt = pexpect  # PEXPECT Class definition for prompt.

        self.am = am  # AM Object

        self.ssh_command = ssh_command  # Variable for current SSH command (str)
        self.telnet_command = telnet_command  # Variable for current Telnet command (str)
        self.timeout = timeout  # Variable for current timeout value (int)
        # self.j_path = setting_file['SETTINGS']['PATH']  # Jumpserver path (lst)
        self.current_prompt = None  # Current prompt (str)
        self.fallback_prompt = None  # Current fallback prompt (Last Jumpserver) (str)
        self.current_connected_host = None  # Name of host currently connected to (str)
        self.conn_type = client_connection_type

        # _j_set = setting_file['JUMPSERVERS']  # Temporary variable for Jumpserver Settings (dct)

        # #Check for jump path. If set, invoke JumphostAgent
        # if len(self.j_path) > 0:
        #     self.ja = JumphostAgent(self.prompt, _j_set, ssh=self.ssh_command,
        #                             telnet=self.telnet_command, timeout=self.timeout,
        #                             account_manager=self.am)
        #     self.prompt = self.ja.connect_jump_path(self.j_path, self.prompt)
        #     self.ssh_command = self.ja.get_settings('SSH')
        #     self.telnet_command = self.ja.get_settings('TELNET')
        #     self.fallback_prompt = self.ja.get_settings('CPROMPT')
        #
        # else:
        #     logging.error("For now connection can only be build through a jumpserver.")
        #     logging.error("Direct connection feature will be build in the near future.")
        #     logging.error("Script will exit now.")
        #     sys.exit(101)
        #
        # Check for jump path. If set, invoke JumphostAgent

        if len(jumpservers) > 0:
            self.connect_jump_path(jumpservers)
        else:
            logging.error("For now connection can only be build through a jumpserver.")
            logging.error("Direct connection feature will be build in the near future.")
            logging.error("Script will exit now.")
            sys.exit(101)

    def test(self):
        pass

    def xyz(self):
        pass