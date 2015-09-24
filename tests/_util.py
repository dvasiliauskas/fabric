import os
import sys
from functools import wraps, partial
from invoke.vendor.six import StringIO

from fabric import Connection
from fabric.main import program as fab_program
from fabric.transfer import Transfer
from mock import patch, Mock
from spec import eq_, trap


# TODO: figure out a non shite way to share Invoke's more beefy copy of same.
@trap
def expect(invocation, out, program=None, test=None):
    if program is None:
        program = fab_program
    program.run("fab {0}".format(invocation), exit=False)
    (test or eq_)(sys.stdout.getvalue(), out)


def mock_remote(out='', err='', exit=0, wait=0):
    def decorator(f):
        @wraps(f)
        @patch('fabric.connection.SSHClient')
        @patch('fabric.runners.time')
        def wrapper(*args, **kwargs):
            args = list(args)
            SSHClient, time = args.pop(), args.pop()

            # Mock out Paramiko bits we expect to be used for most run() calls
            client = SSHClient.return_value
            transport = client.get_transport.return_value
            channel = Mock()
            transport.open_session.return_value = channel
            channel.recv_exit_status.return_value = exit

            # If requested, make exit_status_ready return False the first N
            # times it is called in the wait() loop.
            channel.exit_status_ready.side_effect = (wait * [False]) + [True]

            # Real-feeling IO
            out_file = StringIO(out)
            err_file = StringIO(err)
            def fakeread(count, fileno=None):
                fd = {1: out_file, 2: err_file}[fileno]
                return fd.read(count)
            channel.recv.side_effect = partial(fakeread, fileno=1)
            channel.recv_stderr.side_effect = partial(fakeread, fileno=2)

            # Run test, passing in channel obj (as it's the most useful mock)
            # as last arg
            args.append(channel)
            f(*args, **kwargs)

            # Sanity checks
            client.get_transport.assert_called_with()
            client.get_transport.return_value.open_session.assert_called_with()
            eq_(time.sleep.call_count, wait)
        return wrapper
    return decorator


# TODO: dig harder into spec setup() treatment to figure out why it seems to be
# double-running setup() or having one mock created per nesting level...then we
# won't need this probably.
def mock_sftp(expose_os=False):
    """
    Mock SFTP things, including 'os' & handy ref to SFTPClient instance.

    By default, hands decorated tests a reference to the mocked SFTPClient
    instance and an instantiated Transfer instance, so their signature needs to
    be: ``def xxx(self, sftp, transfer):``.

    If ``expose_os=True``, the mocked ``os`` module is handed in, turning the
    signature to: ``def xxx(self, sftp, transfer, mock_os):``.
    """
    def decorator(f):
        @wraps(f)
        @patch('fabric.transfer.os')
        @patch('fabric.connection.SSHClient')
        def wrapper(*args, **kwargs):
            # Obtain the mocks given us by @patch (and 'self')
            self, Client, mock_os = args
            # SFTP client instance mock
            sftp = Client.return_value.open_sftp.return_value
            # All mock_sftp'd tests care about a Transfer instance
            transfer = Transfer(Connection('host'))
            # Handle common filepath massage actions; tests will assume these.
            def fake_abspath(path):
                return '/local/{0}'.format(path)
            mock_os.path.abspath.side_effect = fake_abspath
            sftp.getcwd.return_value = '/remote'
            # Not super clear to me why the 'wraps' functionality in mock isn't
            # working for this :(
            mock_os.path.basename.side_effect = os.path.basename
            # Pass in mocks as needed
            passed_args = [self, sftp, transfer]
            if expose_os:
                passed_args.append(mock_os)
            # TEST!
            return f(*passed_args)
        return wrapper
    return decorator