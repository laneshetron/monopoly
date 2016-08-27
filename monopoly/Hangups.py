"""Reference chat client for hangups."""

import appdirs
import asyncio
import configargparse
import contextlib
import logging
import os
import sys
import urwid # unfortunate legacy garbage
import readlike

from Bank.Hangouts import Bank
from Bank.Swift import Swift
from Bank.Trumpisms import Trumpisms
from Bank import g

import hangups
from hangups.ui.emoticon import replace_emoticons
from hangups.ui.notify import Notifier
from hangups.ui.utils import get_conv_name
from hangups.ui.utils import add_color_to_scheme


# hangups used to require a fork of urwid called hangups-urwid which may still
# be installed and create a conflict with the 'urwid' package name. See #198.
if urwid.__version__ == '1.2.2-dev':
    sys.exit('error: hangups-urwid package is installed\n\n'
             'Please uninstall hangups-urwid and urwid, and reinstall '
             'hangups.')

CONVERSATION_TYPE_ONE_TO_ONE = 1
CONVERSATION_TYPE_GROUP = 2

CONVERSATION_STATUS_ACTIVE = 2

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
COL_SCHEMES = {
    # Very basic scheme with no colour
    'default': {
        ('active_tab', '', ''),
        ('inactive_tab', 'standout', ''),
        ('msg_date', '', ''),
        ('msg_sender', '', ''),
        ('msg_self', '', ''),
        ('msg_text', '', ''),
        ('status_line', 'standout', ''),
        ('tab_background', 'standout', ''),
    },
    'solarized-dark': {
        ('active_tab', 'light gray', 'light blue'),
        ('inactive_tab', 'underline', 'light green'),
        ('msg_date', 'dark cyan', ''),
        ('msg_sender', 'dark blue', ''),
        ('msg_self', 'light blue', ''),
        ('msg_text', '', ''),
        ('status_line', 'standout', ''),
        ('tab_background', 'underline', 'black'),
    },
}
COL_SCHEME_NAMES = ('active_tab', 'inactive_tab', 'msg_date', 'msg_sender',
                    'msg_self', 'msg_text', 'status_line', 'tab_background')


class ChatUI(object):
    """User interface for hangups."""

    def __init__(self, refresh_token_path, keybindings, palette,
                 palette_colors, datetimefmt, notifier):
        """Start the user interface."""
        self._keys = keybindings
        self._datetimefmt = datetimefmt
        self._notifier = notifier

        set_terminal_title('hangups')

        # These are populated by on_connect when it's called.
        self._conv_list = None  # hangups.ConversationList
        self._user_list = None  # hangups.UserList
        self._notifier = None  # hangups.notify.Notifier
        # Disable UI notifications by default
        self._disable_notifier = True

        try:
            cookies = hangups.auth.get_auth_stdin(refresh_token_path)
        except hangups.GoogleAuthError as e:
            sys.exit('Login failed ({})'.format(e))

        self._client = hangups.Client(cookies)
        self._client.on_connect.add_observer(self._on_connect)

        loop = asyncio.get_event_loop()
        # Enable bracketed paste mode after the terminal has been switched to
        # the alternate screen (after MainLoop.start() to work around bug
        # 729533 in VTE.
        with bracketed_paste_mode():
            try:
                # Returns when the connection is closed.
                loop.run_until_complete(self._client.connect())
            finally:
                loop.close()


    @asyncio.coroutine
    def _on_connect(self):
        """Handle connecting for the first time."""
        print("Client connected.")
        self._user_list, self._conv_list = (
            yield from hangups.build_user_conversation_list(self._client)
        )
        self._conv_list.on_event.add_observer(self._on_event)
        if not self._disable_notifier:
            self._notifier = Notifier(self._conv_list)

        donald = Trumpisms()

        # Start Swift server
        handlers = (self._client, self._conv_list)
        swift = Swift(*handlers)
        self.bank = Bank(*handlers, swift=swift, donald=donald)

    def _on_event(self, conv_event):
        """Open conversation tab for new messages & pass events to notifier."""
        conv = self._conv_list.get(conv_event.conversation_id)

        user = conv.get_user(conv_event.user_id)
        add_tab = all((
            isinstance(conv_event, hangups.ChatMessageEvent),
            not user.is_self,
        ))

        # Set the client as active.
        future = asyncio.async(self._client.set_active())
        future.add_done_callback(lambda future: future.result())

        # Mark the newest event as read.
        future = asyncio.async(conv.update_read_timestamp())
        future.add_done_callback(lambda future: future.result())

        if add_tab:
            asyncio.async(self.bank.receive(conv_event.text, conv, user))
            print(conv_event.text)
            print(user.full_name)

    def _on_quit(self):
        """Handle the user quitting the application."""
        future = asyncio.async(self._client.disconnect())
        future.add_done_callback(lambda future: future.result())


    @staticmethod
    def from_conversation_event(conversation, conv_event, prev_conv_event,
                                datetimefmt):
        """Return MessageWidget representing a ConversationEvent.

        Returns None if the ConversationEvent does not have a widget
        representation.
        """
        user = conversation.get_user(conv_event.user_id)
        # Check whether the previous event occurred on the same day as this
        # event.
        if prev_conv_event is not None:
            is_new_day = (conv_event.timestamp.astimezone(tz=None).date() !=
                          prev_conv_event.timestamp.astimezone(tz=None).date())
        else:
            is_new_day = False
        if isinstance(conv_event, hangups.ChatMessageEvent):
            return MessageWidget(conv_event.timestamp, conv_event.text,
                                 datetimefmt, user, show_date=is_new_day)
        elif isinstance(conv_event, hangups.RenameEvent):
            if conv_event.new_name == '':
                text = ('{} cleared the conversation name'
                        .format(user.first_name))
            else:
                text = ('{} renamed the conversation to {}'
                        .format(user.first_name, conv_event.new_name))
            return MessageWidget(conv_event.timestamp, text, datetimefmt,
                                 show_date=is_new_day)
        elif isinstance(conv_event, hangups.MembershipChangeEvent):
            event_users = [conversation.get_user(user_id) for user_id
                           in conv_event.participant_ids]
            names = ', '.join([user.full_name for user in event_users])
            if conv_event.type_ == hangups.MEMBERSHIP_CHANGE_TYPE_JOIN:
                text = ('{} added {} to the conversation'
                        .format(user.first_name, names))
            else:  # LEAVE
                text = ('{} left the conversation'.format(names))
            return MessageWidget(conv_event.timestamp, text, datetimefmt,
                                 show_date=is_new_day)
        elif isinstance(conv_event, hangups.HangoutEvent):
            text = {
                hangups.HANGOUT_EVENT_TYPE_START: (
                    'A Hangout call is starting.'
                ),
                hangups.HANGOUT_EVENT_TYPE_END: (
                    'A Hangout call ended.'
                ),
                hangups.HANGOUT_EVENT_TYPE_ONGOING: (
                    'A Hangout call is ongoing.'
                ),
            }.get(conv_event.event_type, 'Unknown Hangout call event.')
            return MessageWidget(conv_event.timestamp, text, datetimefmt,
                                 show_date=is_new_day)
        elif isinstance(conv_event, hangups.GroupLinkSharingModificationEvent):
            status_on = hangups.GROUP_LINK_SHARING_STATUS_ON
            status_text = ('on' if conv_event.new_status == status_on
                           else 'off')
            text = '{} turned {} joining by link.'.format(user.first_name,
                                                          status_text)
            return MessageWidget(conv_event.timestamp, text, datetimefmt,
                                 show_date=is_new_day)
        else:
            # conv_event is a generic hangups.ConversationEvent.
            text = 'Unknown conversation event'
            return None

def set_terminal_title(title):
    """Use an xterm escape sequence to set the terminal title."""
    sys.stdout.write("\x1b]2;{}\x07".format(title))


@contextlib.contextmanager
def bracketed_paste_mode():
    """Context manager for enabling/disabling bracketed paste mode."""
    sys.stdout.write('\x1b[?2004h')
    try:
        yield
    finally:
        sys.stdout.write('\x1b[?2004l')


def dir_maker(path):
    """Create a directory if it does not exist."""
    directory = os.path.dirname(path)
    if directory != '' and not os.path.isdir(directory):
        try:
            os.makedirs(directory)
        except OSError as e:
            sys.exit('Failed to create directory: {}'.format(e))


def main(uptime, queues, **kwargs):
    """Main entry point."""
    g.uptime = uptime
    g.queues = queues

    # Build default paths for files.
    dirs = appdirs.AppDirs('hangups', 'hangups')
    default_log_path = os.path.join(dirs.user_log_dir, 'hangups.log')
    default_token_path = os.path.join(dirs.user_cache_dir, 'refresh_token.txt')
    default_config_path = 'hangups.conf'
    user_config_path = os.path.join(dirs.user_config_dir, 'hangups.conf')

    # Create a default empty config file if does not exist.
    dir_maker(user_config_path)
    if not os.path.isfile(user_config_path):
        with open(user_config_path, 'a') as cfg:
            cfg.write("")

    parser = configargparse.ArgumentParser(
        prog='hangups', default_config_files=[default_config_path,
                                              user_config_path],
        formatter_class=configargparse.ArgumentDefaultsHelpFormatter,
        add_help=False,  # Disable help so we can add it to the correct group.
    )
    general_group = parser.add_argument_group('General')
    general_group.add('-h', '--help', action='help',
                      help='show this help message and exit')
    general_group.add('--token-path', default=default_token_path,
                      help='path used to store OAuth refresh token')
    general_group.add('--date-format', default='< %y-%m-%d >',
                      help='date format string')
    general_group.add('--time-format', default='(%I:%M:%S %p)',
                      help='time format string')
    general_group.add('-c', '--config', help='configuration file path',
                      is_config_file=True, default=user_config_path)
    general_group.add('-v', '--version', action='version',
                      version='hangups {}'.format(hangups.__version__))
    general_group.add('-d', '--debug', action='store_true',
                      help='log detailed debugging messages')
    general_group.add('--log', default=default_log_path, help='log file path')
    key_group = parser.add_argument_group('Keybindings')
    key_group.add('--key-next-tab', default='ctrl d',
                  help='keybinding for next tab')
    key_group.add('--key-prev-tab', default='ctrl u',
                  help='keybinding for previous tab')
    key_group.add('--key-close-tab', default='ctrl w',
                  help='keybinding for close tab')
    key_group.add('--key-quit', default='ctrl e',
                  help='keybinding for quitting')
    key_group.add('--key-menu', default='ctrl n',
                  help='keybinding for context menu')
    key_group.add('--key-up', default='k',
                  help='keybinding for alternate up key')
    key_group.add('--key-down', default='j',
                  help='keybinding for alternate down key')
    notification_group = parser.add_argument_group('Notifications')
    notification_group.add('-n', '--disable-notifications',
                           action='store_true',
                           help='disable desktop notifications')
    notification_group.add('-D', '--discreet-notifications',
                           action='store_true',
                           help='hide message details in notifications')

    # add color scheme options
    col_group = parser.add_argument_group('Colors')
    col_group.add('--col-scheme', choices=COL_SCHEMES.keys(),
                  default='default', help='colour scheme to use')
    col_group.add('--col-palette-colors', choices=('16', '88', '256'),
                  default=16, help='Amount of available colors')
    for name in COL_SCHEME_NAMES:
        col_group.add('--col-' + name.replace('_', '-') + '-fg',
                      help=name + ' foreground color')
        col_group.add('--col-' + name.replace('_', '-') + '-bg',
                      help=name + ' background color')

    args = parser.parse_args()

    # Create all necessary directories.
    for path in [kwargs.get('log') or args.log,
                 kwargs.get('token_path') or args.token_path]:
        dir_maker(path)

    logging.basicConfig(filename=kwargs.get('log') or args.log,
                        level=logging.DEBUG if args.debug else logging.WARNING,
                        format=LOG_FORMAT)
    # urwid makes asyncio's debugging logs VERY noisy, so adjust the log level:
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    datetimefmt = {'date': args.date_format,
                   'time': args.time_format}

    # setup color scheme
    palette_colors = int(args.col_palette_colors)

    col_scheme = COL_SCHEMES[args.col_scheme]
    for name in COL_SCHEME_NAMES:
        col_scheme = add_color_to_scheme(col_scheme, name,
                                         getattr(args, 'col_' + name + '_fg'),
                                         getattr(args, 'col_' + name + '_bg'),
                                         palette_colors)

    if not args.disable_notifications:
        notifier = Notifier(args.discreet_notifications)
    else:
        notifier = None

    try:
        ChatUI(
            kwargs.get('token_path') or args.token_path, {
                'next_tab': args.key_next_tab,
                'prev_tab': args.key_prev_tab,
                'close_tab': args.key_close_tab,
                'quit': args.key_quit,
                'menu': args.key_menu,
                'up': args.key_up,
                'down': args.key_down
            }, col_scheme, palette_colors, datetimefmt, notifier
        )
    except KeyboardInterrupt:
        sys.exit('Caught KeyboardInterrupt, exiting abnormally')
    except:
        # urwid will prevent some exceptions from being printed unless we use
        # print a newline first.
        print('')
        raise


if __name__ == '__main__':
    main()
