"""
Configure structured logging.

Copyright (C) 2020 Nicholas H.Tollervey (ntoll@ntoll.org).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>
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
