OpenRank
========

Minimal script for retrieving the weighted cumulative GPA from PowerSchool Home Access.

Requirements
------------
- Python 3.9 or newer
- Dependencies listed in `requirements.txt`

Setup
-----
1. (Optional) Create and activate a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`

Usage
-----
1. Run `python fetch.py`.
2. Enter your Home Access Center username and password when prompted.
3. The script prints the weighted cumulative GPA if login succeeds.

Notes
-----
- The default district is `Bentonville School District`; update `DISTRICT` in `fetch.py` if needed.
- Your credentials are only used for the active session and are not stored.
