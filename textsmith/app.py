"""
Server application and configuration for web based layer of TextSmith.

Copyright (C) 2020 Nicholas H.Tollervey.
"""
import os
import sys
import asyncio
import structlog  # type: ignore
import quart.flask_patch  # type: ignore # noqa
import uuid
import asyncio_redis  # type: ignore
import textsmith.log  # noqa
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
from flask_wtf import FlaskForm, RecaptchaField  # type: ignore
from wtforms import validators  # type: ignore
from wtforms.fields import PasswordField, BooleanField  # type: ignore
from wtforms.fields.html5 import EmailField  # type: ignore
from functools import wraps
from textsmith.pubsub import PubSub
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
# ReCaptcha support.
app.config.update(
    {
        "RECAPTCHA_PUBLIC_KEY": os.environ.get(
            "RECAPTCHA_PUBLIC_KEY", "CHANGEME"
        ),
        "RECAPTCHA_PRIVATE_KEY": os.environ.get(
            "RECAPTCHA_PRIVATE_KEY", "CHANGEME"
        ),
    }
)
# Email settings.
app.config.update(
    {
        "EMAIL_ADDRESS": os.environ.get("TEXTSMITH_EMAIL_ADDRESS", "CHANGEME"),
        "EMAIL_PASSWORD": os.environ.get(
            "TEXTSMITH_EMAIL_PASSWORD", "CHANGEME"
        ),
        "EMAIL_HOST": os.environ.get("TEXTSMITH_EMAIL_HOST", "CHANGEME"),
        "EMAIL_PORT": int(os.environ.get("TEXTSMITH_EMAIL_PORT", "CHANGEME")),
    }
)


# ---------- WEB FORM DEFINITIONS


class SignUp(FlaskForm):
    """
    Gather basic information about a new user.
    """

    email = EmailField(
        _("Email address"),
        [
            validators.InputRequired(message=_("Required.")),
            validators.Email(message=_("Not a valid email address.")),
        ],
        render_kw={"autofocus": True},
    )
    accept = BooleanField(
        _("I accept the code of conduct"),
        [validators.InputRequired(_("Please agree to our code of conduct."))],
    )
    recaptcha = RecaptchaField()


class SetPassword(FlaskForm):
    """
    Allows a user to set and confirm a new password.
    """

    password1 = PasswordField(
        _("Password"),
        [
            validators.InputRequired(message=_("Required.")),
            validators.EqualTo(
                "password2", message=_("Passwords must match.")
            ),
            validators.Length(
                min=8, message=_("Minimum password length is 8.")
            ),
        ],
        render_kw={"autofocus": True},
    )
    password2 = PasswordField(
        _("Confirm Password"), [validators.InputRequired(_("Required."))]
    )


class LogIn(FlaskForm):
    """
    Gather required information to identify a user.
    """

    email = EmailField(
        _("Email address"),
        [
            validators.InputRequired(),
            validators.Email(message=_("Not a valid email address.")),
        ],
        render_kw={"autofocus": True},
    )
    password = PasswordField(
        _("Password"), [validators.InputRequired(_("Required."))]
    )


# ---------- APP EVENTS
@app.before_serving
async def on_start(app: Quart = app) -> None:
    """
    Read configuration and setup the application.

    Log that the application is starting, for status update purposes.
    """
    logger.msg("Starting application.")
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
        logic = Logic(
            datastore,
            app.config["EMAIL_HOST"],
            app.config["EMAIL_PORT"],
            app.config["EMAIL_ADDRESS"],
            app.config["EMAIL_PASSWORD"],
        )
        app.logic = logic  # type: ignore
        pubsub = PubSub(subscriber)
        app.pubsub = pubsub  # type: ignore
        app.parser = Parser(logic)  # type: ignore
        logger.msg("Waiting for connections.")
    except Exception as ex:  # pragma: no cover
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
    return request.accept_languages.best_match(["de", "fr", "en"])


# ----------  ERROR HANDLERS
@app.errorhandler(404)
async def page_not_found(e):  # pragma: no cover
    """
    Handle 404 Not Found.
    """
    logger.msg(
        "404",
        method=request.method,
        path=request.path,
        locale=get_locale(),
        headers=dict(request.headers),
        user_id=session.get("user_id"),
    )
    return await render_template("404.html"), 404


@app.errorhandler(500)
async def internal_server_error(e):  # pragma: no cover
    """
    Handle 500 Internal Server Error.
    """
    logger.msg(
        "500",
        method=request.method,
        path=request.path,
        locale=get_locale(),
        headers=dict(request.headers),
        user_id=session.get("user_id"),
    )
    return await render_template("500.html"), 500


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
        user_id=session.get("user_id"),
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
        user_id=session.get("user_id"),
    )
    return await render_template("help.html")


@app.route("/conduct", methods=["GET"])
async def conduct():
    """
    Render the code of conduct page.
    """
    logger.msg(
        "Access",
        endpoint="/conduct",
        locale=get_locale(),
        headers=dict(request.headers),
        user_id=session.get("user_id"),
    )
    return await render_template("conduct.html")


@app.route("/privacy", methods=["GET"])
async def privacy():
    """
    Render the privacy statement page.
    """
    logger.msg(
        "Access",
        endpoint="/privacy",
        locale=get_locale(),
        headers=dict(request.headers),
        user_id=session.get("user_id"),
    )
    return await render_template("privacy.html")


@app.route("/welcome", methods=["GET"])
async def welcome():
    """
    Render the welcome page when users have completed sign-up.
    """
    logger.msg(
        "Access",
        endpoint="/welcome",
        locale=get_locale(),
        headers=dict(request.headers),
        user_id=session.get("user_id"),
    )
    form = LogIn()
    return await render_template("welcome.html", form=form)


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
    messages off a message queue for the current user.
    """
    while True:
        message = await current_app.pubsub.get_message(user_id)
        await websocket.send(message)
        logger.msg(
            "Outgoing message.",
            user_id=user_id,
            connection_id=connection_id,
            message=message,
        )


async def receiving(user_id: int, connection_id: str):
    """
    Parse incoming data. Any resulting output will but put in the user's
    message queue.
    """
    while True:
        data = await websocket.receive()
        logger.msg(
            "Incoming message.",
            user_id=user_id,
            connection_id=connection_id,
            message=data,
        )
        await current_app.parser.eval(user_id, connection_id, data)


def require_user(func):
    """
    A decorator for websocket connections.

    Ensure the user_id is in the session. Otherwise, abort the connection.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        if user_id:
            logger.msg("User session.", user_id=user_id)
            return await func(*args, **kwargs)
        else:
            logger.msg(
                "401",
                method=websocket.method,
                path=websocket.path,
                headers=dict(websocket.headers),
            )
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
            await current_app.pubsub.unsubscribe(
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
    logger.msg(
        "Log in.",
        endpoint="/login",
        locale=get_locale(),
        headers=dict(request.headers),
        user_id=session.get("user_id"),
        method=request.method,
    )
    form = LogIn()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user_id = await current_app.logic.verify_credentials(email, password)
        if user_id:
            session["user_id"] = user_id
            await current_app.logic.set_last_seen(user_id)
            return redirect(url_for("client"))
    error = None
    if request.method == "POST":
        error = _("Could not log you in. Please try again.")
    return await render_template("login.html", error=error, form=form)


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
    form = SignUp()
    logger.msg(
        "Sign up.",
        endpoint="/signup",
        locale=get_locale(),
        headers=dict(request.headers),
        user_id=session.get("user_id"),
        method=request.method,
    )
    valid = form.validate_on_submit()
    email_error = _("This email address is already taken.")
    if form.email.data and not valid:
        # Ensure the email uniqueness is async checked even if form is bad.
        email_exists = await current_app.logic.check_email(form.email.data)
        if email_exists:
            form.email.errors.append(email_error)
    if valid:
        email = form.email.data
        email_exists = await current_app.logic.check_email(email)
        if not email_exists:
            await current_app.logic.create_user(email)
            logger.msg("Signed up new user.", email=email)
            return redirect(url_for("thanks"))
        else:
            form.email.errors.append(email_error)
    return await render_template("signup.html", form=form)


@app.route("/confirm/<uuid:confirmation_token>", methods=["GET", "POST"])
async def confirm(confirmation_token):
    """
    Given a valid confirmation token (uuid) created when the user signed up,
    gather password information for the user or raise a 404.
    """
    valid_token = await current_app.logic.check_token(confirmation_token)
    if not valid_token:
        abort(404)
    form = SetPassword()
    if form.validate_on_submit():
        password = form.password1.data
        await current_app.logic.confirm_user(str(confirmation_token), password)
        return redirect(url_for("welcome"))
    return await render_template(
        "confirm_user.html", form=form, confirmation_token=confirmation_token
    )
