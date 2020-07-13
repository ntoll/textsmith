"""
Tests for the Quart application layer (web based frontend).

Copyright (C) 2020 Nicholas H.Tollervey
"""
import pytest  # type: ignore
from unittest import mock
from uuid import uuid4
from quart.testing import WebsocketResponse


@pytest.fixture(name="app", scope="function")
async def _app():
    from textsmith.app import app

    mock_redis = mock.AsyncMock()
    mock_subscriber = mock.AsyncMock()
    mock_redis.start_subscribe.return_value = mock_subscriber
    mock_message = mock.MagicMock()
    mock_message.channel = "1"
    mock_message.value = "A message"
    mock_subscriber.next_published = mock.AsyncMock(return_value=mock_message)
    mock_pool = mock.AsyncMock(return_value=mock_redis)
    mock_pubsub = mock.MagicMock()
    mock_pubsub.subscribe = mock.AsyncMock()
    mock_pubsub.unsubscribe = mock.AsyncMock()
    with mock.patch(
        "textsmith.app.asyncio_redis.Pool.create", mock_pool
    ), mock.patch("textsmith.app.PubSub"):
        await app.startup()
    app.testing = True
    app.logic = mock.MagicMock()
    app.pubsub = mock_pubsub
    app.parser = mock.MagicMock()
    app.config["WTF_CSRF_ENABLED"] = False
    yield app
    await app.shutdown()


@pytest.mark.asyncio
async def test_static_pages(app):
    """
    "Static" endpoints, that only render templates via an HTTP GET result in
    a 200 response.
    """
    client = app.test_client()
    static_endpoints = [
        "/",
        "/thanks",
        "/help",
        "/conduct",
        "/privacy",
        "/welcome",
    ]
    for endpoint in static_endpoints:
        response = await client.get(endpoint)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_client_not_logged_in(app):
    """
    A request to the /client endpoint that doesn't have a logged in session
    associated with it is redirected to the /login endpoint.
    """
    client = app.test_client()
    response = await client.get("/client")
    assert response.status_code == 302  # redirect...
    assert response.location == "/login"  # ...to /login


@pytest.mark.asyncio
async def test_client_logged_in(app):
    """
    If the session indicates the user is logged in, render the client.
    """
    client = app.test_client()
    async with client.session_transaction() as local_session:
        local_session["user_id"] = "1"
    response = await client.get("/client")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_websocket_no_session(app):
    """
    A websocket connection without a logged in user session results in a 401
    response.
    """
    client = app.test_client()
    async with client.websocket("/ws") as test_websocket:
        try:
            await test_websocket.send("hello")
        except WebsocketResponse as error:
            assert error.response.status_code == 401


@pytest.mark.asyncio
async def test_websocket(app):
    """
    A websocket connection is made with a logged-in session, and the mocked
    "pong" response from the parser for incoming data is received as expected.
    """
    client = app.test_client()
    app.parser.eval = mock.AsyncMock()
    app.pubsub.get_message = mock.AsyncMock(return_value="pong")
    async with client.session_transaction() as local_session:
        local_session["user_id"] = "1"
    async with client.websocket("/ws") as test_websocket:
        await test_websocket.send("ping")
        result = await test_websocket.receive()
        assert result == "pong"


@pytest.mark.asyncio
async def test_login_get(app):
    """
    Getting the login page: all ok.
    """
    client = app.test_client()
    response = await client.get("/login")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_login_post_bad(app):
    """
    If an error is encountered in the POSTed login form, the expected error
    message is displayed.
    """
    client = app.test_client()
    app.logic.verify_credentials = mock.AsyncMock(return_value=False)
    data = {
        "email": "foo@bar.com",
        "password": "password123",
    }
    response = await client.post("/login", json=data)
    content = await response.get_data()
    content = content.decode("utf-8")
    assert "Could not log you in. Please try again." in content
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_login_post_ok(app):
    """
    A valid POSTed login form results in a redirect to the /client endpoint.
    """
    client = app.test_client()
    app.logic.verify_credentials = mock.AsyncMock(return_value=1)
    app.logic.set_last_seen = mock.AsyncMock()
    data = {
        "email": "foo@bar.com",
        "password": "password123",
    }
    response = await client.post("/login", json=data)
    assert response.status_code == 302  # redirect...
    assert response.location == "/client"  # ...to /client
    # Session is updated.
    async with client.session_transaction() as local_session:
        assert local_session["user_id"] == 1
    # User login time set.
    app.logic.set_last_seen.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_logout(app):
    """
    The user_id is removed from the session and the user is redirected to the
    home page.
    """
    client = app.test_client()
    async with client.session_transaction() as local_session:
        local_session["user_id"] = "1"
    response = await client.get("/logout")
    assert response.status_code == 302  # redirect...
    assert response.location == "/"  # ...to /
    # Session is updated.
    async with client.session_transaction() as local_session:
        assert local_session.get("user_id") is None


@pytest.mark.asyncio
async def test_signup_get(app):
    """
    Getting the signup page: contains the expected form.
    """
    client = app.test_client()
    response = await client.get("/signup")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_signup_email_already_taken(app):
    """
    The signup page won't allow a valid email address to be re-used.
    """
    client = app.test_client()
    app.logic.check_email = mock.AsyncMock(return_value=True)
    data = {"email": "foo@bar.com", "accept": "accept"}
    response = await client.post("/signup", json=data)
    content = await response.get_data()
    content = content.decode("utf-8")
    assert "This email address is already taken." in content
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_signup_invalid_email_already_taken(app):
    """
    Even if the signup form is invalid, the email address is still checked for
    uniqueness.
    """
    client = app.test_client()
    app.logic.check_email = mock.AsyncMock(return_value=True)
    data = {"email": "foo@bar.com", "accept": None}
    response = await client.post("/signup", json=data)
    content = await response.get_data()
    content = content.decode("utf-8")
    assert "This email address is already taken." in content
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_signup_valid(app):
    """
    Signup with valid details results in a redirect to the /thanks endpoint.
    """
    client = app.test_client()
    app.logic.check_email = mock.AsyncMock(return_value=False)
    app.logic.create_user = mock.AsyncMock()
    data = {"email": "foo@bar.com", "accept": "accept"}
    response = await client.post("/signup", json=data)
    assert response.status_code == 302  # redirect...
    assert response.location == "/thanks"  # ...to /thanks
    app.logic.create_user.assert_called_once_with("foo@bar.com")


@pytest.mark.asyncio
async def test_confirm_invalid_token(app):
    """
    If the uuid isn't valid, returns a 404.
    """
    client = app.test_client()
    response = await client.get("/confirm/not-a-uuid")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_confirm_get_invalid_token(app):
    """
    Getting the confirmation page with a valid uuid which isn't a currently
    "live" token results in a 404.
    """
    token = str(uuid4())
    client = app.test_client()
    app.logic.check_token = mock.AsyncMock(return_value=False)
    response = await client.get(f"/confirm/{token}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_confirm_get(app):
    """
    Getting the confirmation page with a valid uuid: contains the expected
    form.
    """
    token = str(uuid4())
    client = app.test_client()
    app.logic.check_token = mock.AsyncMock(return_value=True)
    response = await client.get(f"/confirm/{token}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_confirm(app):
    """
    A valid POST to the endpoint results in a redirect to the /welcome
    endpoint.
    """
    token = str(uuid4())
    client = app.test_client()
    app.logic.check_token = mock.AsyncMock(return_value=True)
    app.logic.confirm_user = mock.AsyncMock()
    data = {
        "password1": "password",
        "password2": "password",
    }
    response = await client.post(f"/confirm/{token}", json=data)
    assert response.status_code == 302  # redirect...
    assert response.location == "/welcome"  # ...to /welcome
    app.logic.confirm_user.assert_called_once_with(token, "password")
