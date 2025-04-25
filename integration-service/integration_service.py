# integration_service.py
from flask import Flask, request, jsonify
import psycopg2
import json

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

# CREATE - Receive sales data
@app.route('/sales-data', methods=['POST'])
def receive_sales():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        required_fields = ['agent_id', 'sale_amount', 'product_code', 'sale_date']
        
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

        # Insert sales data
        cursor.execute(
            """INSERT INTO sales_data 
            (agent_id, sale_amount, product_code, sale_date, additional_details) 
            VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (data['agent_id'], data['sale_amount'], data['product_code'], 
             data['sale_date'], json.dumps(data.get('additional_details', {})))
        )

        sale_id = cursor.fetchone()[0]
        conn.commit()
        
        return jsonify({
            "message": "Sales data received",
            "sale_id": sale_id,
            "agent_id": data['agent_id']
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# READ - Get all sales for an agent
@app.route('/sales/<int:agent_id>', methods=['GET'])
def get_sales(agent_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if agent exists
        cursor.execute("SELECT id FROM agents WHERE id = %s", (agent_id,))
        if cursor.fetchone() is None:
            return jsonify({"error": "Agent not found"}), 404

        # Get sales data
        cursor.execute(
            """SELECT id, sale_amount, product_code, sale_date, additional_details 
            FROM sales_data WHERE agent_id = %s""",
            (agent_id,)
        )
        
        sales = []
        for sale in cursor.fetchall():
            sales.append({
                "id": sale[0],
                "agent_id": agent_id,
                "sale_amount": float(sale[1]),
                "product_code": sale[2],
                "sale_date": sale[3].isoformat() if sale[3] else None,
                "additional_details": sale[4] if sale[4] else {}
            })
        
        return jsonify(sales), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# UPDATE - Update specific sale
@app.route('/sales/<int:sale_id>', methods=['PUT'])
def update_sale(sale_id):
    conn = None
    cursor = None
    try:
        data = request.get_json()
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if sale exists
        cursor.execute("SELECT id FROM sales_data WHERE id = %s", (sale_id,))
        if cursor.fetchone() is None:
            return jsonify({"error": "Sale record not found"}), 404

        # Build update query dynamically based on provided fields
        update_fields = []
        update_values = []
        valid_fields = ['sale_amount', 'product_code', 'sale_date', 'additional_details']
        
        for field in valid_fields:
            if field in data:
                update_fields.append(f"{field} = %s")
                if field == 'additional_details':
                    update_values.append(json.dumps(data[field]))
                else:
                    update_values.append(data[field])

        if not update_fields:
            return jsonify({"error": "No valid fields provided for update"}), 400

        update_values.append(sale_id)
        update_query = f"""UPDATE sales_data SET {', '.join(update_fields)} 
                          WHERE id = %s RETURNING agent_id"""

        cursor.execute(update_query, update_values)
        agent_id = cursor.fetchone()[0]
        conn.commit()
        
        return jsonify({
            "message": "Sale record updated",
            "sale_id": sale_id,
            "agent_id": agent_id
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# DELETE - Remove specific sale
@app.route('/sales/<int:sale_id>', methods=['DELETE'])
def delete_sale(sale_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if sale exists
        cursor.execute("SELECT id FROM sales_data WHERE id = %s", (sale_id,))
        if cursor.fetchone() is None:
            return jsonify({"error": "Sale record not found"}), 404

        cursor.execute("DELETE FROM sales_data WHERE id = %s RETURNING agent_id", (sale_id,))
        agent_id = cursor.fetchone()[0]
        conn.commit()
        
        return jsonify({
            "message": "Sale record deleted",
            "sale_id": sale_id,
            "agent_id": agent_id
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8082)
