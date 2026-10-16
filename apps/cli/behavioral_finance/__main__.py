"""
behavioral-finance/__main__.py
================================
Entry point — allows running as:  python -m behavioral-finance <command>

Clean Architecture: delegates immediately to the interface layer.
"""

from .interface.cli import main

if __name__ == "__main__":
    main()
