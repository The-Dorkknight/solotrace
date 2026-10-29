# Security

SoloTrace is a desktop program that reads and writes local files (`.solotrace` boards, KiCad `.kicad_mod` footprints, export files) and sends nothing over the network.

If you find a problem that could harm a user (for example a crafted board or footprint file that makes the program overwrite files, or G-code that could move a machine outside the area you set), please report it privately with GitHub's "Report a vulnerability" button on the Security tab of this repository instead of opening a public issue.

This is early software and comes with no warranty. A laser must never be left unattended and G-code should always be checked in your laser software's preview before burning.
