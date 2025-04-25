import json

import psycopg2
import redshift_connector
import os

def sync_to_redshift():
    try:
        print("Connecting to Postgres...")
        pg_conn = psycopg2.connect(
            host=os.getenv("PG_HOST", "ls-1da58d02ca2520ec50e600aa762e63871c25220d.c5g2628m27rg.ap-south-1.rds.amazonaws.com"),
            dbname=os.getenv("PG_DB", "moon-agent"),
            user=os.getenv("PG_USER", "moonagentuser"),
            password=os.getenv("PG_PASSWORD", "DWIJRwybuh038&$")
        )
        pg_cur = pg_conn.cursor()
        pg_cur.execute("SELECT * FROM performance_reports ORDER BY created_at DESC LIMIT 1")
        row = pg_cur.fetchone()
        row = list(row)
        if isinstance(row[3], dict):
            row[3] = json.dumps(row[3])

        if not row:
            print("No data to sync.")
            return

        print("Connecting to Redshift...")
        rs_conn = redshift_connector.connect(
            host=os.getenv("REDSHIFT_HOST", "kce-cluster.cd9fbf7fnazh.ap-south-1.redshift.amazonaws.com"),
            database=os.getenv("REDSHIFT_DB", "moon-agent"),
            user=os.getenv("REDSHIFT_USER", "awsuser"),
            password=os.getenv("REDSHIFT_PASSWORD", "DWIJRwybuh038&$")
        )
        rs_cur = rs_conn.cursor()

        # Update with your actual columns
        rs_cur.execute("""
                INSERT INTO performance_reports (id, report_date, frequency, report_data, created_at)
                VALUES (%s, %s, %s, %s, %s)
            """, row)
        rs_conn.commit()

        print("✅ Sync successful!")
    except Exception as e:
        print("❌ Sync failed:", str(e))
        raise

if __name__ == "__main__":
    sync_to_redshift()
