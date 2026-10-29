# Contributing

SoloTrace is a work in progress. Bug reports, test boards that route badly and notes from real laser runs are the most useful things you can send.

- **Bug or odd result:** open an issue with the form (version from Help > About or `--version`, your platform, and the `.solotrace` file if you can share it).
- **Laser results:** please say which settings you used and what came out. Nobody has run this G-code on a real Phecda yet, so real numbers are valuable.
- **Code:** keep the standard-library-only rule (Python 3.8+, tkinter, no required third-party packages). Run the tests before you send a change:
  `python3 src/main.py selftest` (or `python3 -m unittest discover -s tests`; the GUI tests need a display, e.g. `xvfb-run -a`).
- Every source file keeps the Required Notice header.

**Licence of contributions:** by sending a contribution you agree that it falls under the same licence as the project (PolyForm Noncommercial 1.0.0, see `LICENSE.md`), and that you have the right to send it.
