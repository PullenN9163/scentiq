import os

os.environ.setdefault("SCENTIQ_ENV", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:password@localhost/scentiq_test")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
