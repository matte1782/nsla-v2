# tests/conftest.py
import sys
import os

# Aggiunge la directory root al path per risolvere gli import
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
