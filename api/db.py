import os
import psycopg

def get_conn():
    return psycopg.connect(
        host=os.environ["PGHOST"],
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        dbname=os.environ["PGDATABASE"],
        port=int(os.environ.get("PGPORT", 5432)),
        sslmode="require",
        connect_timeout=5,
    )
