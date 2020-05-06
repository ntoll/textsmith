"""
Server application and configuration for web based layer of TextSmith.

Copyright (C) 2019 Nicholas H.Tollervey.
"""
import os
import sys
import asyncio
import structlog  # type: ignore
import quart.flask_patch  # type: ignore # noqa
import uuid
import asyncio_redis  # type: ignore
from logging import getLogger
from quart import (
    Quart,
    render_template,
    request,
    redirect,
    url_for,
    session,
    websocket,
    abort,
    current_app,
)
from quart.logging import default_handler
from flask_babel import Babel  # type: ignore
from flask_babel import gettext as _  # type: ignore
from flask_seasurf import SeaSurf  # type: ignore
from functools import wraps
from textsmith.pubsub import PubSub
from textsmith.models import Models
from textsmith.datastore import DataStore
from textsmith.logic import Logic
from textsmith.parser import Parser


__all__ = ["app"]


logger = structlog.get_logger()
logger.msg("Starting application.")


# Remove built-in logging.
getLogger("quart.app").removeHandler(default_handler)


# ---------- APP CONFIGURATION
app = Quart(__name__)
app.config.update(
    {
        "SECRET_KEY": os.environ.get("TEXTSMITH_KEY", "CHANGEME"),
        "DEBUG": os.environ.get("TEXTSMITH_DEBUG") is not None,
    }
)
# i18n support.
babel = Babel(app)
# CSRF mitigation.
csrf = SeaSurf(app)


# ---------- APP EVENTS
@app.before_serving
async def on_start(app: Quart = app) -> None:
    """
    Read configuration and setup the application.

    Log that the application is starting, for status update purposes.
    """
    # The Redis connection pool for interacting with the database.
    host = os.environ.get("TEXTSMITH_REDIS_HOST", "localhost")
    port = int(os.environ.get("TEXTSMITH_REDIS_PORT", 6379))
    password = os.environ.get("TEXTSMITH_REDIS_PASSWORD", None)
    poolsize = int(os.environ.get("TEXTSMITH_REDIS_POOLSIZE", 10))
    logger.msg("Redis Config.", host=host, port=port, poolsize=poolsize)
    try:
        redis = await asyncio_redis.Pool.create(
            host=host, port=port, password=password, poolsize=poolsize
        )
        logger.msg(
            "Connected to Redis.",
            redis_host=host,
            redis_port=port,
            redis_poolsize=poolsize,
        )
        subscriber = await redis.start_subscribe()
        # Assemble objects and inject into the global app scope.
        datastore = DataStore(redis)
        models = Models()
        logic = Logic(models, datastore)
        pubsub = PubSub(subscriber)
        app.pubsub = pubsub  # type: ignore
        app.parser = Parser(logic)  # type: ignore
        logger.msg("Waiting for connections.")
    except Exception as ex:
        # If the app can't connect to Redis, log this and exit.
        logger.msg("ABORT. Failed to connect to Redis.", exc_info=ex)
        loop = asyncio.get_running_loop()
        loop.stop()
        loop.close()
        sys.exit(1)


@app.after_serving
async def on_stop():
    """
    Log that the application is stopping, for status update purposes.
    """
    logger.msg("Stopped.")


@babel.localeselector
def get_locale():
    """
    Get the locale for the current request.
    """
    # if a user is logged in, use the locale from the user settings
    # user = getattr(g, 'user', None)
    # if user is not None:
    #    return user.locale
    # otherwise try to guess the language from the user accept
    # header the browser transmits.  We support de/fr/en in this
    # example.  The best match wins.
    return request.accept_languages.best_match(["de", "fr", "en"])


# ----------  STATIC ENDPOINTS
@app.route("/", methods=["GET"])
async def home():
    """
    Render the homepage.
    """
    logger.msg(
        "Access",
        endpoint="/",
        locale=get_locale(),
        headers=dict(request.headers),
    )
    return await render_template("home.html")


@app.route("/thanks", methods=["GET"])
async def thanks():
    """
    Render the thanks for signing up page.
    """
    logger.msg(
        "Access",
        endpoint="/thanks",
        locale=get_locale(),
        headers=dict(request.headers),
    )
    return await render_template("thanks.html")


@app.route("/help", methods=["GET"])
async def help():
    """
    Render the help page.
    """
    logger.msg(
        "Access",
        endpoint="/help",
        locale=get_locale(),
        headers=dict(request.headers),
    )
    return await render_template("help.html")


@app.route("/client", methods=["GET"])
async def client():
    """
    Render the client assets needed by the browser to connect to the
    websocket. Will only work if the user is logged in.
    """
    if session.get("user_id"):
        logger.msg(
            "Access",
            endpoint="/client",
            locale=get_locale(),
            headers=dict(request.headers),
            user_id=session.get("user_id"),
        )
        return await render_template("client.html")
    else:
        return redirect(url_for("login"))


# ----------  WEBSOCKET HANDLERS
async def sending(user_id: int, connection_id: str) -> None:
    """
    Handle the sending of messages to a connected websocket. Simply read
    messages off a message bus for the current user.
    """
    while True:
        message = current_app.pubsub.get_message(user_id)
        if message:
            await websocket.send(message)
            logger.msg(
                "Outgoing message.",
                user_id=user_id,
                connection_id=connection_id,
                message=message,
            )
        else:
            await asyncio.sleep(0.0001)


async def receiving(user_id, connection_id):
    """
    Parse incoming data.
    """
    while True:
        data = await websocket.receive()
        logger.msg(
            "Incoming message.",
            user_id=user_id,
            connection_id=connection_id,
            message=data,
        )
        await current_app.parser.eval(user_id, data)


def require_user(func):
    """
    A decorator for websocket connections.

    Ensure the user_id is in the session. Otherwise, abort the connection.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        user_id = session.get("user_id", None)
        if user_id:
            logger.msg("User session.", user_id=user_id)
            return await func(*args, **kwargs)
        else:
            abort(401)

    return wrapper


def collect_websocket(func):
    """
    A decorator for websocket connections.

    Annotate the user_id and connection_id to the websocket object, for later
    use. Log details about the connection starting/closing.

    Ensure the user_id is added to the connected_users set upon connection,
    and removed when the connection is dropped.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Get the user's id from the session.
        websocket.user_id = session.get("user_id")
        # Make an id to uniquely identify this connection.
        websocket.connection_id = str(uuid.uuid4())
        # Log the connection client's details (mostly headers).
        logger.msg(
            "Websocket open.",
            locale=get_locale(),
            user_id=websocket.user_id,
            connection_id=websocket.connection_id,
            url=websocket.url,
            headers=dict(websocket.headers),
        )
        await current_app.pubsub.subscribe(
            websocket.user_id, websocket.connection_id
        )
        try:
            return await func(*args, **kwargs)
        finally:
            # Unsubscribe from messages published for this user.
            await app.pubsub.unsubscribe(
                websocket.user_id, websocket.connection_id
            )
            logger.msg(
                "Websocket closed.",
                user_id=websocket.user_id,
                connection_id=websocket.connection_id,
            )

    return wrapper


@app.websocket("/ws")
@require_user
@collect_websocket
async def ws():
    """
    Handle separate connections to the websocket endpoint.
    """
    # The two tasks for sending and receiving data on this connection need
    # to be created and gathered.
    producer = asyncio.create_task(
        sending(websocket.user_id, websocket.connection_id)
    )
    consumer = asyncio.create_task(
        receiving(websocket.user_id, websocket.connection_id)
    )
    await asyncio.gather(producer, consumer)


# ----------  USER STATE HANDLERS
@app.route("/login", methods=["GET", "POST"])
async def login():
    """
    Checks the credentials and creates a session.
    """
    error = None
    if request.method == "POST":
        form = await request.form
        username = form.get("username")
        password = form.get("password")
        user_id = await current_app.logic.verify_password(username, password)
        if user_id:
            session["user_id"] = user_id
            await current_app.logic.set_last_login(user_id)
            return redirect(url_for("client"))
        error = _("Could not log you in. Please try again.")
    return await render_template("login.html", error=error)


@app.route("/logout", methods=["GET"])
async def logout():
    """
    Clear the user_id from the cookie.
    """
    if "user_id" in session:
        logger.msg("User logout.", user_id=session["user_id"])
        del session["user_id"]
    return redirect(url_for("home"))


@app.route("/signup", methods=["GET", "POST"])
async def signup():
    """
    Renders and handles the signup page where new users sign up.

    If the content of the form is good create the user and then send them
    to the thanks page with further instructions.
    """
    error = {}
    if request.method == "POST":
        form = await request.form
        username = form.get("username")
        password = form.get("password")
        confirm_password = form.get("confirm_password")
        email = form.get("email")
        username_ok = await current_app.logic.check_username(username)
        if username_ok:
            error["username"] = _("The username is already taken.")
        if password != confirm_password:
            error["password"] = _("The passwords don't match.")
        if not error:
            await current_app.logic.create_user(username, password, email)
            return redirect(url_for("thanks"))
    return await render_template("signup.html", error=error)