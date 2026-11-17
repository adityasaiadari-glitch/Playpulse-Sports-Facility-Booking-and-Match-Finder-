"""
PlayPulse backend package  (Unit II: Modules & Packages)

The backend is split into small modules, each with one job:
    exceptions.py  - custom exception classes            (Unit IV)
    validators.py  - regex checks for user input         (Unit III)
    slots.py       - date/time slot logic + a generator  (Unit III + Unit II)
    models.py      - classes: Venue, User, Booking, Game (Unit II: OOP)
    storage.py     - reading/writing JSON & CSV files    (Unit IV)
    services.py    - the "business rules" of the app
    analytics.py   - NumPy + pandas + Matplotlib charts  (Unit III + Unit V)

app.py (Flask) only talks to services.py, never to the files directly.
"""
