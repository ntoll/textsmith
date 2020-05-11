"""
Configure structured logging.

Copyright (C) 2020 Nicholas H.Tollervey.
"""
import structlog  # type: ignore
import platform


# Gather host system information.
host = platform.uname()


def host_info(logger, log_method, event_dict: dict) -> dict:
    """
    Add useful information to each log entry about the system upon which the
    application is running.
    """
    event_dict["hostname"] = host.node  # hostname of the computer.
    event_dict["system"] = host.system  # OS name, e.g. "Linux".
    event_dict["release"] = host.release  # OS release name.
    event_dict["version"] = host.version  # OS release number.
    event_dict["machine"] = host.machine  # machine architecture, e.g. "i386".
    event_dict["processor"] = host.processor  # processor model.
    return event_dict


# Each log will be timestamped (ISO_8601), have details of the host system,
# nicely format exceptions if found via the 'exc_info' key, and render as JSON.
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        host_info,
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]
)
