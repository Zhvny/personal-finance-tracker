"""
advanced_features/main.py
===========================
Entry point — delegates to interface layer.
Zero business logic here (Clean Architecture).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from interface.cli import main

if __name__ == "__main__":
    main()
