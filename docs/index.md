# TextSmith

A multi-user collaborative platform for creating and inhabiting text based
literary worlds.

**This is very much a work in progress.**

## Developer Setup

This project uses Python 3.7+.

1. Ensure you have [Redis](https://redis.io/) installed.
2. Clone the [repository](https://github.com/ntoll/textsmith).
3. Create and start a new virtual environment.
4. `pip install -r requirements.txt`
5. Type `make` to see a list of common developer related tasks. For instance,
   to run the full test suite and code checks type: `make check`.

The application expects certain configuration settings to be found in the
environment. These are (with default settings within parenthesis):

* `TEXTSMITH_REDIS_HOST` (`"localhost"`) - the server running Redis.
* `TEXTSMITH_REDIS_PORT` (`6379`) - the port to use to connect to Redis.
* `TEXTSMITH_REDIS_PASSWORD` (`None`) - the password to use to connect to
  Redis.
* `TEXTSMITH_REDIS_POOLSIZE` (`10`) - the number of connections in the Redis
  connection pool.
* `TEXTSMITH_KEY` (`"CHANGEME"`) - the secret key used by the web application
  for cryptographic operations.
* `TEXTSMITH_DEBUG` (`False`) - the debug flag which results in detailed debug
  information from the web application. This flag is assumed to be `True` if
  any value is set in the environment variable.
* `RECAPTCHA_PUBLIC_KEY` (`"CHANGEME"`) - the public key for the reCaptcha v2
  challenge in the signup form.
* `RECAPTCHA_PRIVATE_KEY` (`"CHANGEME"`) - the private key for the reCaptcha
  v2 challenge in the signup form.
* `TEXTSMITH_EMAIL_ADDRESS` (`"CHANGEME"`) - the email address of the account
  TextSmith uses to send emails to users.
* `TEXTSMITH_EMAIL_PASSWORD` (`"CHANGEME"`) - the password for the email
  account TextSmith uses to send emails to users.
* `TEXTSMITH_EMAIL_HOST` (`"CHANGEME"`) - the host for the email account
  TextSmith uses to send emails to users.
* `TEXTSMITH_EMAIL_PORT` (`"CHANGEME"`) - the port for the email account
  TextSmith uses to send emails to users.

To run TextSmith, `make run` and connect to the
[local server](http://localhost:8000/) with your browser. If the `make` command
doesn't work, try the following command from the shell:
`hypercorn textsmith.app:app`.

JSON based structured logging is emitted to stdout. Each log entry is on a
single line and contains a timestamp and details of the system upon which the
application is running.

## Contents
```eval_rst
.. toctree::
   :maxdepth: 2

   contributing.md
   code_of_conduct.md
   architecture.md
   api.md
   license.md
   authors.md
   acknowledgements.md
```
