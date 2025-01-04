#!/usr/bin/env python3
import argparse
import logging
import sys
import signal
import gi
import json
gi.require_version('Playerctl', '2.0')
from gi.repository import Playerctl, GLib

logger = logging.getLogger(__name__)

def write_output(text, player=None):
    logger.info('Writing output')

    output = {'text': text,
              'class': 'custom-' + (player.props.player_name if player else 'no-media'),
              'alt': 'No media' if player is None else player.props.player_name}

    sys.stdout.write(json.dumps(output) + '\n')
    sys.stdout.flush()

def on_play(player, status, manager):
    logger.info('Received new playback status')
    on_metadata(player, player.props.metadata, manager)

def on_metadata(player, metadata, manager):
    logger.info('Received new metadata')
    track_info = ''

    if player.props.player_name == 'spotify' and \
            'mpris:trackid' in metadata.keys() and \
            ':ad:' in player.props.metadata['mpris:trackid']:
        track_info = 'AD PLAYING'
    elif player.get_artist() != '' and player.get_title() != '':
        track_info = '{artist} - {title}'.format(artist=player.get_artist(),
                                                 title=player.get_title())
    else:
        track_info = player.get_title()

    if player.props.status != 'Playing' and track_info:
        track_info = ' ' + track_info
    write_output(track_info, player)

def on_player_appeared(manager, player, selected_player=None):
    if player is not None:
        init_player(manager, player)
    else:
        logger.debug("New player appeared")

def on_player_vanished(manager, player):
    logger.info('Player has vanished')

    # Track whether any player is still active
    player_found = False
    for player_name in manager.props.player_names:
        player_found = True
        break

    # If no players are left, output "There is no media"
    if not player_found:
        write_output("There is no media")
    else:
        # If there's still an active player, just flush output
        sys.stdout.write('\n')
        sys.stdout.flush()

def init_player(manager, name):
    logger.debug('Initialize player: {player}'.format(player=name.name))
    player = Playerctl.Player.new_from_name(name)
    player.connect('playback-status', on_play, manager)
    player.connect('metadata', on_metadata, manager)
    manager.manage_player(player)
    on_metadata(player, player.props.metadata, manager)

def signal_handler(sig, frame):
    logger.debug('Received signal to stop, exiting')
    sys.stdout.write('\n')
    sys.stdout.flush()
    sys.exit(0)

def parse_arguments():
    parser = argparse.ArgumentParser()

    # Increase verbosity with every occurrence of -v
    parser.add_argument('-v', '--verbose', action='count', default=0)

    # Define for which player we're listening
    parser.add_argument('--player')

    return parser.parse_args()

def main():
    arguments = parse_arguments()

    # Initialize logging
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG,
                        format='%(name)s %(levelname)s %(message)s')

    # Logging is set by default to WARN and higher.
    # With every occurrence of -v it's lowered by one
    logger.setLevel(max((3 - arguments.verbose) * 10, 0))

    # Log the sent command line arguments
    logger.debug('Arguments received {}'.format(vars(arguments)))

    manager = Playerctl.PlayerManager()
    loop = GLib.MainLoop()

    manager.connect('name-appeared', lambda *args: on_player_appeared(*args))
    manager.connect('player-vanished', on_player_vanished)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    # Track if any player is active
    player_found = False

    for player in manager.props.player_names:
        init_player(manager, player)
        player_found = True

    # If no player was found, show "There is no media"
    if not player_found:
        write_output("There is no media")

    loop.run()

if __name__ == '__main__':
    main()
