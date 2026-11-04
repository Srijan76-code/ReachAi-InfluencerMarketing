import os

# Tests run the Inngest app in dev mode: production mode needs a signing key, which tests never have.
os.environ.setdefault("INNGEST_DEV", "1")
