"""Isolated browser-test application. This module is never the deployment entrypoint."""

from test_discovery import RSS

from app.main import create_app

app = create_app()
app.state.fetch_feed = lambda _: RSS
