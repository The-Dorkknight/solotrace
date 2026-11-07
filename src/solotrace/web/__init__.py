# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""SoloTrace web UI: the same editor in a browser, for computers where tkinter is missing or broken.

WORK IN PROGRESS: many features may be broken.

``session.py`` is the editor without any window toolkit (board, undo, tools, selection, the panels
as plain data); ``server.py`` serves ``static/`` on 127.0.0.1 and turns HTTP requests into session
commands. Nothing leaves the computer: the server only listens on the loopback address.
"""
