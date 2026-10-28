import os
import tempfile

# Must run before `app` is imported anywhere, so tests never touch the real database.
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
