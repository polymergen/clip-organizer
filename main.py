"""Redirect: run UnifiedTools clip viewer. Use launch_viewer.bat or UnifiedTools directly."""
import os
import runpy
import sys

_UT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "UnifiedTools"))
sys.argv[0] = os.path.join(_UT, "main.py")
os.chdir(_UT)
runpy.run_path(sys.argv[0], run_name="__main__")
