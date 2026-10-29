# Third-party notes

The PolyForm Noncommercial licence in `LICENSE.md` covers only the code and documents written for SoloTrace. Everything below keeps its own licence and belongs to its own owners.

**No affiliation.** SoloTrace is an independent hobby project. It is not made, approved or supported by Elegoo, KiCad, Abacom, JLCPCB or anyone else named here. Product and project names are used only to say what the software works with.

## What SoloTrace uses

| Item | How it is used | Licence |
| --- | --- | --- |
| Python and tkinter | Runs the program; the program needs nothing else | Python Software Foundation licence ([python.org/psf/license](https://docs.python.org/3/license.html)) |
| [gerbonara](https://pypi.org/project/gerbonara/) | Optional, tests only: one test re-reads the exported Gerber and drill files. Not bundled, not needed to run the app | See the project page |
| [Pillow](https://pypi.org/project/pillow/) | Optional, development only: `tools/make_icons.py` draws the icon set. Not bundled | See the project page |
| Chromium + Playwright, ImageMagick | Only used while making the README screenshots and the Pages site check; not part of the project | Their own licences |

## File formats and machines

- **Gerber RS-274X, Excellon** are open industry formats; SoloTrace writes them from the published format descriptions.
- **KiCad `.kicad_mod`** footprint files can be imported. Only the text format is read; no KiCad code or library is included. Footprint libraries you import keep the licence they were published under: check it before sharing boards that embed them.
- **G-code for GRBL-style controllers.** The Elegoo Phecda is assumed to behave like a GRBL machine (it is used with LaserGRBL and LightBurn). That is an assumption from public product information, not from a manual for the controller. See [DESIGN_NOTES.md](DESIGN_NOTES.md).

## Research

The ideas behind the router (A* maze routing, rip-up and reroute, PathFinder negotiated congestion, topological routing, planarisation) are described in the research notes with links: [docs/research/pcb-app-research-and-plan.md](docs/research/pcb-app-research-and-plan.md). No code from Freerouting, KiCad or any other router was used; the router here is written from scratch.
