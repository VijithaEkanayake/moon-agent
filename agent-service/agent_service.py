# agent_service.py
import os
import json
import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)

# PostgreSQL connection parameters
DB_HOST = "localhost"
DB_NAME = "moon-agent"
DB_USER = "admin"
DB_PASS = "password"

def get_db_connection():
    conn = psycopg2.connect(
        DB_HOST = os.environ.get("DB_HOST", "localhost"),
        DB_NAME = os.environ.get("DB_NAME", "moon-agent"),
        DB_USER = os.environ.get("DB_USER", "admin"),
        DB_PASS = os.environ.get("DB_PASS", "password"),
    )
    return conn

# CREATE
@app.route('/agents', methods=['POST'])
def create_agent():
    conn = None
    cursor = None
    try:
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()

        # Convert products to JSON string if it's a list or string
        products = data.get("products", [])
        if isinstance(products, str):
            products = [p.strip() for p in products.split(",")]
        products_str = json.dumps(products)

        cursor.execute(
            "INSERT INTO agents (name, code, details, products) VALUES (%s, %s, %s, %s) RETURNING id",
            (data["name"], data["code"], data["details"], products_str))

        new_id = cursor.fetchone()[0]
        conn.commit()
        return jsonify({"id": new_id, "name": data["name"], "code": data["code"], 
                       "details": data["details"], "products": products}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# READ (Single)
@app.route('/agents/<int:agent_id>', methods=['GET'])
def get_agent(agent_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name, code, details, products FROM agents WHERE id = %s", (agent_id,))
        agent = cursor.fetchone()
        
        if agent is None:
            return jsonify({"error": "Agent not found"}), 404
        
        # Parse products from text to list
        products = json.loads(agent[4]) if agent[4] else []
            
        return jsonify({
            "id": agent[0],
            "name": agent[1],
            "code": agent[2],
            "details": agent[3],
            "products": products
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# READ (All)
@app.route('/agents', methods=['GET'])
def get_all_agents():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name, code, details, products FROM agents")
        agents = cursor.fetchall()
        
        agents_list = []
        for agent in agents:
            # Parse products from text to list
            products = json.loads(agent[4]) if agent[4] else []
            agents_list.append({
                "id": agent[0],
                "name": agent[1],
                "code": agent[2],
                "details": agent[3],
                "products": products
            })
            
        return jsonify(agents_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# UPDATE
@app.route('/agents/<int:agent_id>', methods=['PUT'])
def update_agent(agent_id):
    conn = None
    cursor = None
    try:
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if agent exists
        cursor.execute("SELECT id FROM agents WHERE id = %s", (agent_id,))
        if cursor.fetchone() is None:
            return jsonify({"error": "Agent not found"}), 404

        # Convert products to JSON string if it's a list or string
        products = data.get("products", [])
        if isinstance(products, str):
            products = [p.strip() for p in products.split(",")]
        products_str = json.dumps(products)

        cursor.execute(
            """UPDATE agents 
            SET name = %s, code = %s, details = %s, products = %s 
            WHERE id = %s""",
            (data["name"], data["code"], data["details"], products_str, agent_id)
        )
        
        conn.commit()
        return jsonify({
            "id": agent_id,
            "name": data["name"],
            "code": data["code"],
            "details": data["details"],
            "products": products
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# DELETE
@app.route('/agents/<int:agent_id>', methods=['DELETE'])
def delete_agent(agent_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if agent exists
        cursor.execute("SELECT id FROM agents WHERE id = %s", (agent_id,))
        if cursor.fetchone() is None:
            return jsonify({"error": "Agent not found"}), 404

        cursor.execute("DELETE FROM agents WHERE id = %s", (agent_id,))
        conn.commit()
        
        return jsonify({"message": "Agent deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
