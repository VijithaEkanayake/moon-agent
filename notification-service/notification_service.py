# notification_service.py
from flask import Flask, request, jsonify
import psycopg2
import json
from datetime import datetime

app = Flask(__name__)

# PostgreSQL connection parameters
DB_HOST = "localhost"
DB_NAME = "moon-agent"
DB_USER = "admin"
DB_PASS = "password"

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=5432
    )
    return conn

@app.route('/send-notification', methods=['POST'])
def send_notification():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        required_fields = ['agent_id', 'message']
        
        # Validate required fields
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if agent exists
        cursor.execute("SELECT id FROM agents WHERE id = %s", (data['agent_id'],))
        if cursor.fetchone() is None:
            return jsonify({"error": "Agent not found"}), 404

        # Get notification preferences
        cursor.execute(
            "SELECT email_notifications, sms_notifications FROM notification_preferences WHERE agent_id = %s",
            (data['agent_id'],)
        )
        prefs = cursor.fetchone()
        
        # Store notification in database
        notification_type = data.get('notification_type', 'reminder')
        cursor.execute(
            """INSERT INTO notifications 
            (agent_id, message, notification_type, status, sent_at) 
            VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (data['agent_id'], data['message'], notification_type, 'sent', datetime.utcnow())
        )
        notification_id = cursor.fetchone()[0]
        conn.commit()

        # Prepare response with delivery methods
        delivery_methods = []
        if prefs:
            if prefs[0]:  # email_notifications
                delivery_methods.append("email")
            if prefs[1]:  # sms_notifications
                delivery_methods.append("sms")
        else:
            # Default to email if no preferences set
            delivery_methods.append("email")

        return jsonify({
            "message": f"Notification sent to agent {data['agent_id']}",
            "notification_id": notification_id,
            "delivery_methods": delivery_methods,
            "content": data['message']
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

@app.route('/check-target-achievements', methods=['POST'])
def check_target_achievements():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if 'agent_id' not in data:
            return jsonify({"error": "Missing agent_id"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get agent's sales data and target threshold
        cursor.execute("""
            SELECT np.sales_target_threshold, COALESCE(SUM(sd.sale_amount), 0) as total_sales
            FROM notification_preferences np
            LEFT JOIN sales_data sd ON np.agent_id = sd.agent_id 
                AND sd.sale_date >= DATE_TRUNC('month', CURRENT_DATE)
            WHERE np.agent_id = %s
            GROUP BY np.sales_target_threshold
        """, (data['agent_id'],))
        
        result = cursor.fetchone()
        if not result:
            return jsonify({"error": "Agent preferences not found"}), 404

        threshold, total_sales = result
        target_achieved = total_sales >= threshold

        if target_achieved:
            # Send congratulatory notification
            message = f"Congratulations! You've achieved your monthly sales target of ${threshold:.2f}"
            cursor.execute(
                """INSERT INTO notifications 
                (agent_id, message, notification_type, status, sent_at) 
                VALUES (%s, %s, 'achievement', 'sent', %s)""",
                (data['agent_id'], message, datetime.utcnow())
            )
            conn.commit()

        return jsonify({
            "agent_id": data['agent_id'],
            "target_threshold": float(threshold),
            "current_sales": float(total_sales),
            "target_achieved": target_achieved,
            "notification_sent": target_achieved
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

@app.route('/notification-preferences/<int:agent_id>', methods=['GET', 'PUT'])
def handle_preferences(agent_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if agent exists
        cursor.execute("SELECT id FROM agents WHERE id = %s", (agent_id,))
        if cursor.fetchone() is None:
            return jsonify({"error": "Agent not found"}), 404

        if request.method == 'GET':
            cursor.execute(
                "SELECT email_notifications, sms_notifications, push_notifications, sales_target_threshold FROM notification_preferences WHERE agent_id = %s",
                (agent_id,)
            )
            prefs = cursor.fetchone()
            if not prefs:
                return jsonify({"message": "Using default notification preferences"}), 200

            return jsonify({
                "email_notifications": prefs[0],
                "sms_notifications": prefs[1],
                "push_notifications": prefs[2],
                "sales_target_threshold": float(prefs[3])
            }), 200

        elif request.method == 'PUT':
            data = request.get_json()
            update_fields = []
            update_values = []
            valid_fields = ['email_notifications', 'sms_notifications', 
                           'push_notifications', 'sales_target_threshold']

            for field in valid_fields:
                if field in data:
                    update_fields.append(f"{field} = %s")
                    update_values.append(data[field])

            if not update_fields:
                return jsonify({"error": "No valid fields provided for update"}), 400

            # Check if preferences exist
            cursor.execute("SELECT 1 FROM notification_preferences WHERE agent_id = %s", (agent_id,))
            if cursor.fetchone():
                # Update existing preferences
                update_query = f"UPDATE notification_preferences SET {', '.join(update_fields)} WHERE agent_id = %s"
                update_values.append(agent_id)
            else:
                # Insert new preferences
                update_query = f"""
                    INSERT INTO notification_preferences 
                    (agent_id, {', '.join(field.split(' = ')[0] for field in update_fields)}) 
                    VALUES (%s, {', '.join(['%s']*len(update_fields))}
                """
                update_values.insert(0, agent_id)

            cursor.execute(update_query, update_values)
            conn.commit()

            return jsonify({"message": "Notification preferences updated"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

@app.route('/notifications/<int:agent_id>', methods=['GET'])
def get_notifications(agent_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if agent exists
        cursor.execute("SELECT id FROM agents WHERE id = %s", (agent_id,))
        if cursor.fetchone() is None:
            return jsonify({"error": "Agent not found"}), 404

        # Get notifications
        cursor.execute("""
            SELECT id, message, notification_type, status, created_at, sent_at, read_at
            FROM notifications
            WHERE agent_id = %s
            ORDER BY created_at DESC
            LIMIT 50
        """, (agent_id,))
        
        notifications = []
        for note in cursor.fetchall():
            notifications.append({
                "id": note[0],
                "message": note[1],
                "type": note[2],
                "status": note[3],
                "created_at": note[4].isoformat() if note[4] else None,
                "sent_at": note[5].isoformat() if note[5] else None,
                "read_at": note[6].isoformat() if note[6] else None
            })

        return jsonify(notifications), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8083)
