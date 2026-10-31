import os
import tempfile

# Must run before `app` is imported anywhere, so tests never touch the real database.
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
# The real .env may switch an LLM on; tests must never reach a model (an empty value is not overridden by load_dotenv).
os.environ["LLM_PROVIDER"] = ""
os.environ["LLM_API_KEY"] = ""
