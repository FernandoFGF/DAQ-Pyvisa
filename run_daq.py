#!/usr/bin/env python3
"""
DAQ-Pyvisa launcher (Python side).

The Windows launcher is run_daq.bat. This script is a thin Python
wrapper that just imports the main app; run_daq.bat does the
preflight (venv, pip, config.yaml) so the banners don't have to
be duplicated in two places.
"""

import daq_gui_main  # noqa: F401  (import has the side effect of running the app)
