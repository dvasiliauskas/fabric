"""
Tests concerned with the ``fab`` tool & how it overrides Invoke defaults.
"""

import os

from mock import patch
from spec import Spec, assert_contains, eq_
from invoke.util import cd

from fabric import Connection
from fabric.main import Fab, program as fab_program

from _util import expect, mock_remote


class Fab_(Spec):
    def version_output_contains_our_name_plus_deps(self):
        expect(
            "--version",
            r"""
Fabric .+
Paramiko .+
Invoke .+
""".strip(),
            test=assert_contains
        )

    def help_output_says_fab(self):
        expect("--help", "Usage: fab", test=assert_contains)

    def loads_fabfile_not_tasks(self):
        "Loads fabfile.py, not tasks.py"
        with cd(os.path.join(os.path.dirname(__file__), '_support')):
            expect(
                "--list",
                """
Available tasks:

  build
  deploy

""".lstrip()
            )

    def exposes_hosts_flag_in_help(self):
        expect("--help", "-H STRING, --hosts=STRING", test=assert_contains)

    @mock_remote()
    def executes_remainder_as_anonymous_task(self, chan):
        # contextmanager because hard to thread extra mocks into the decorator
        with patch('fabric.main.Connection', wraps=Connection) as MConnection:
            fab_program.run("fab -H myhost -- whoami", exit=False)
            # Did we connect to the host?
            # (not using assert_called_with because using mock.ANY causes funky
            # blowups when comparing with Config objects)
            eq_(MConnection.call_args[1]['host'], 'myhost')
            # Did we execute the command?
            chan.exec_command.assert_called_with('whoami')