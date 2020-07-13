"""
Default attribute and function definitions for textual worlds.

Copyright (C) 2020 Nicholas H.Tollervey.
"""
import structlog  # type: ignore
import re
from flask_babel import lazy_gettext as _  # type: ignore


logger = structlog.get_logger()


#: Default indicator at the start of a string to indicate it is a script.
IS_SCRIPT = "#!"


#: The attribute containing the object's primary name.
NAME = "name"
#: The attribute containing a list of the object's aliases.
ALIAS = ".alias"
#: The attribute giving the full description of an object.
DESCRIPTION = "description"
#: The attribute containing the summary (short) description of an object.
SUMMARY = "summary"
#: The attribute to indicate an object is a user.
IS_USER = ".user"
#: The attribute to indicate an object's owner.
OWNER = ".owner"
#: The attribute to flag if an object can be moved.
MOVABLE = "movable"
#: The attribute to indicate if an object is an exit.
IS_EXIT = ".exit"
#: The attribute to indicate the destination of an exit.
DESTINATION = "destination"
#: The attribute describing movement through an exit.
TRAVEL = "travel"
#: The attribute to indicate the object is a room.
IS_ROOM = ".room"
#: The attribute describing a user's entrance to a room.
ENTER_ROOM = "enter_room"
#: The attribute describing a user's exit from a room.
EXIT_ROOM = "exit_room"
#: The attribute flagging that an object is deleted.
IS_DELETED = ".deleted"
#: The attribute describing how an object says.
SAYS = "say"
#: The attribute describing how an object shouts.
SHOUTS = "shout"
#: The attribute describing how an object emotes.
EMOTE = "emote"
#: The attribute describing how an object tells.
TELL = "tell"
#: The attribute describing how an object emits output.
EMIT = "emit"


#: Default aliases for the current user.
USER_ALIASES = [
    _("me"),
    _("myself"),
]
#: Default aliases for the current location.
ROOM_ALIASES = [
    _("here"),
    _("hither"),
]
#: Regex for matching object ids. e.g. #1234.
MATCH_OBJECT_ID = re.compile(r"^#\d+$")


#: Default messages of last resort when the user's input cannot be parsed. Huh?
HUH = [
    _("Huh? That doesn't make sense to me."),
    _("I don't understand that."),
    _("Nope. No idea what you're on about."),
    _("I don't know what you mean."),
    _("Try explaining that in a way I can understand."),
    _("Yeah right... as if I know what you're on about. :-)"),
    _("Let me try tha... nope."),
    _("Ummm... you're not making sense. Again, but with feeling!"),
    _("No idea. Try giving me something I understand."),
    _("Huh? I don't understand. Maybe ask someone for help?"),
    _("Try using commands I understand."),
]
