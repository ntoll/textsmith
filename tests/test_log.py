"""
Tests for log configuration.

Copyright (C) 2020 Nicholas H.Tollervey
"""
import platform
from textsmith import log


def test_host_info():
    """
    Ensure the correct values are annotated to the event_dict:

    * "hostname" - hostname of the computer.
    * "system" - the OS name, e.g. "Linux".
    * "release" - OS's release name.
    * "version" - OS's version number.
    * "machine" - computer's machine architecture, e.g. "i386".
    * "processor" - the computer's processer model.
    """
    event_dict = {}
    log.host_info(None, None, event_dict)
    host_info = platform.uname()
    assert event_dict["hostname"] == host_info.node
    assert event_dict["system"] == host_info.system
    assert event_dict["release"] == host_info.release
    assert event_dict["version"] == host_info.version
    assert event_dict["machine"] == host_info.machine
    assert event_dict["processor"] == host_info.processor
