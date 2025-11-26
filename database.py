import psycopg2
from psycopg2.extras import RealDictCursor

DB_URL = "postgresql://postgres:3moreR@132##$$!!@db.rjhtgcorsuxvctablycl.supabase.co:5432/postgres"

def get_connection():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
