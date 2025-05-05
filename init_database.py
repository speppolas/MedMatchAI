#!/usr/bin/env python3
"""
Script wrapper per l'inizializzazione del database di MedMatchINT.
Richiama lo script di inizializzazione nella cartella scripts.

Utilizzo: python init_database.py [opzioni]
"""

import sys
from scripts.db_init import main

if __name__ == "__main__":
    sys.exit(main())