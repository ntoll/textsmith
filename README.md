# TextSmith

A multi-user platform for creating, programming and interacting within text
based literary worlds.

A version of this game is hosted at
[http://textsmith.org/](http://textsmith.org).

To run the game locally:

* Within a virtualenv gather the requirements: `pip install -r
  requirements.txt`
* Use the following command to launch the server: `make run`
* Connect to the [local server](http://localhost:8000) via your browser.

If the `make` command doesn't work, try the following command from the shell:
`hypercorn textsmith.app:app`.

The game database is stored in Redis. On first run, the game will create a
minimum-viable database if the expected data is not available.

Configuration is via the following environment variables (with default values
within parenthesis, if the variable is not set):

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

JSON based structured logging is emitted to stdout. Each log entry is on a
single line and contains a timestamp and details of the system upon which the
application is running.

The Makefile comes with lots of helpful commands. For instance, to run the
complete test suite type, `make check`. Type just `make` to see a full list of
all the available commands.

To generate the developer documentation type, `make docs`. Developer
documentation is created using Sphinx and the source for the documentation can
be found in the `docs` directory in the root of the project.
