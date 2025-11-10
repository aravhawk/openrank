OpenRank
========

Minimal web experience for retrieving the latest transcript details and showcasing a live GPA leaderboard powered by
PowerSchool Home Access.

Requirements
------------
- Python 3.9 or newer
- Dependencies listed in `requirements.txt`

Setup
-----
1. (Optional) Create and activate a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`

Running the leaderboard
-----------------------
1. Run `pip install -r requirements.txt`.
2. Start the development server with `flask --app app run` (or `python app.py` for debug mode).
3. Visit `http://127.0.0.1:5000` in your browser.

### Accounts and data persistence

- The application stores credentials and GPA data in `data/students.json`.
- A default administrator account (`admin` / `admin123`) is pre-seeded for local testing.
- When a student signs in, their GPA is refreshed using the scraper and their record is persisted for later sessions.
- Administrators can refresh GPAs for every stored student with a single click.

Notes
-----
- The default district is `Bentonville School District`; students can override it during sign-in.
- For one-off GPA retrieval without the web UI you can still run `python fetch.py`.
