from flask import Flask, jsonify
import psycopg2
import json
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import atexit

app = Flask(__name__)

# PostgreSQL connection
DB_CONFIG = {
    "host": "ls-1da58d02ca2520ec50e600aa762e63871c25220d.c5g2628m27rg.ap-south-1.rds.amazonaws.com",
    "dbname": "moon-agent",
    "user": "moonagentuser",
    "password": "DWIJRwybuh038&$",
    "port": 5432
}

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def generate_daily_reports():
    print("Generating daily reports...")
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()

        # Best performing teams (top 10 agents)
        cur.execute("""
            SELECT a.id, a.name, SUM(s.sale_amount) as total_sales
            FROM agents a
            JOIN sales_data s ON a.id = s.agent_id
            WHERE s.sale_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY a.id
            ORDER BY total_sales DESC
            LIMIT 10
        """)
        top_performers = [{"agent_id": r[0], "name": r[1], "sales": float(r[2])} for r in cur.fetchall()]

        # Product performance
        cur.execute("""
            SELECT product_code, COUNT(*), SUM(sale_amount)
            FROM sales_data
            WHERE sale_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY product_code
            ORDER BY SUM(sale_amount) DESC
        """)
        product_performance = [{
            "product": r[0],
            "transactions": r[1],
            "revenue": float(r[2])
        } for r in cur.fetchall()]

        # Target achievements
        cur.execute("""
            SELECT a.id, a.name, SUM(s.sale_amount) as total_sales,
                   np.sales_target_threshold as target,
                   SUM(s.sale_amount) >= np.sales_target_threshold as achieved
            FROM agents a
            JOIN sales_data s ON a.id = s.agent_id
            JOIN notification_preferences np ON a.id = np.agent_id
            WHERE s.sale_date >= DATE_TRUNC('month', CURRENT_DATE)
            GROUP BY a.id, np.sales_target_threshold
        """)
        target_achievements = [{
            "agent_id": r[0], "name": r[1], "sales": float(r[2]),
            "target": float(r[3]), "achieved": r[4]
        } for r in cur.fetchall()]

        # Branch Performance
        cur.execute("""
            SELECT b.id, b.name, SUM(s.sale_amount) as total_sales
            FROM branches b
            JOIN agents a ON b.id = a.branch_id
            JOIN sales_data s ON a.id = s.agent_id
            WHERE s.sale_date >= DATE_TRUNC('month', CURRENT_DATE)
            GROUP BY b.id
            ORDER BY total_sales DESC
        """)
        branch_performance = [{
            "branch_id": r[0], "name": r[1], "total_sales": float(r[2])
        } for r in cur.fetchall()]

        # Store report
        report_date = datetime.now().date()
        report_data = {
            "top_performers": top_performers,
            "product_performance": product_performance,
            "target_achievements": target_achievements,
            "branch_performance": branch_performance,
            "generated_at": datetime.now().isoformat()
        }

        cur.execute("""
            INSERT INTO performance_reports (report_date, report_type, data)
            VALUES (%s, %s, %s)
        """, (report_date, "daily", json.dumps(report_data)))

        conn.commit()
        print("Daily reports generated successfully")
    except Exception as e:
        print(f"Error generating reports: {str(e)}")
    finally:
        if conn:
            conn.close()

# Scheduled tasks
scheduler = BackgroundScheduler()
scheduler.add_job(func=generate_daily_reports, trigger="interval", minutes=1)  # Run daily at 2AM
scheduler.start()

# Shut down scheduler when exiting
atexit.register(lambda: scheduler.shutdown())

# API Endpoints
@app.route('/trigger-report', methods=['POST'])
def trigger_report():
    try:
        generate_daily_reports()
        return jsonify({"message": "Report generation triggered successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/reports/daily', methods=['GET'])
def get_daily_reports():
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT report_date, data 
            FROM performance_reports
            WHERE report_type = 'daily'
            ORDER BY report_date DESC
            LIMIT 7
        """)
        reports = [{
            "date": r[0].isoformat(),
            "data": r[1]
        } for r in cur.fetchall()]
        return jsonify(reports)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/performance/agents', methods=['GET'])
def get_agent_performance():
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT a.id, a.name, ap.period_start, ap.period_end, 
                   ap.total_sales, ap.target_achieved
            FROM agent_performance ap
            JOIN agents a ON ap.agent_id = a.id
            ORDER BY ap.period_start DESC, ap.total_sales DESC
            LIMIT 100
        """)

        performance = [{
            "agent_id": r[0], "name": r[1],
            "period": {"start": r[2].isoformat(), "end": r[3].isoformat()},
            "total_sales": float(r[4]),
            "target_achieved": r[5]
        } for r in cur.fetchall()]

        return jsonify(performance)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081)
