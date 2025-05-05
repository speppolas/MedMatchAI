#!/usr/bin/env python3
"""
Script wrapper per l'aggiornamento dei trial clinici di MedMatchINT.
Richiama lo script di aggiornamento nella cartella scripts.

Utilizzo: python update_trials.py [opzioni]
"""

import sys
from scripts.update_trials import main

if __name__ == "__main__":
    sys.exit(main())