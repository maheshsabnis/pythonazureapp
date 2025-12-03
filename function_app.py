# python
import os
import json
import datetime
import decimal
import logging
from dotenv import load_dotenv
import azure.functions as func
import pyodbc
# Load environment variables from .env file
load_dotenv()
app = func.FunctionApp()
# Private helper to get a DB connection
def _get_connection():
    conn_str = os.getenv("SQL_CONNECTION_STRING")
    if conn_str:
        return pyodbc.connect(conn_str, autocommit=False)
    server = os.getenv("SQL_SERVER")
    database = os.getenv("SQL_DATABASE")
    user = os.getenv("SQL_USER")
    password = os.getenv("SQL_PASSWORD")
    driver = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server")
    print(f"SERVER={server}, DATABASE={database}, USER={user}, PASSWORD={'****' if password else None}, DRIVER={driver}")

    print(f"The Connection String is {os.getenv("SQL_CONNECTION_STRING")}")
    
    
    if not (server and database and user and password):
        raise RuntimeError("Database connection settings are not fully configured.")
   # conn_str = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};UID={user};PWD={password}"
    conn_str = os.getenv("SQL_CONNECTION_STRING")

    return pyodbc.connect(conn_str, autocommit=False)
# Private helper to convert a DB row to a dict
def _row_to_dict(row, columns):
    result = {}
    for idx, col in enumerate(columns):
        val = row[idx]
        if isinstance(val, (datetime.datetime, datetime.date)):
            result[col] = val.isoformat()
        elif isinstance(val, decimal.Decimal):
            result[col] = float(val)
        else:
            result[col] = val
    return result

@app.route(route="products", methods=["GET","POST","PUT","DELETE"], auth_level=func.AuthLevel.FUNCTION)
def products(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Products endpoint called. Method: %s", req.method)
    try:
        if req.method == "GET":
            # support ?product_record_id= or ?product_id=
            record_id = req.params.get("product_record_id") or req.params.get("id")
            product_id = req.params.get("product_id")
            with _get_connection() as conn:
                cursor = conn.cursor()
                if record_id:
                    cursor.execute("SELECT ProductRecordId, ProductId, ProductName, CategoryName, Description, UnitPrice FROM ProductInfo WHERE ProductRecordId = ?", record_id)
                    row = cursor.fetchone()
                    if not row:
                        return func.HttpResponse(json.dumps({"error": "Not found"}), status_code=404, mimetype="application/json")
                    cols = [c[0] for c in cursor.description]
                    return func.HttpResponse(json.dumps(_row_to_dict(row, cols)), status_code=200, mimetype="application/json")
                if product_id:
                    cursor.execute("SELECT ProductRecordId, ProductId, ProductName, CategoryName, Description, UnitPrice FROM ProductInfo WHERE ProductId = ?", product_id)
                    rows = cursor.fetchall()
                    cols = [c[0] for c in cursor.description]
                    results = [_row_to_dict(r, cols) for r in rows]
                    return func.HttpResponse(json.dumps(results), status_code=200, mimetype="application/json")
                cursor.execute("SELECT ProductRecordId, ProductId, ProductName, CategoryName, Description, UnitPrice FROM ProductInfo ORDER BY ProductRecordId")
                rows = cursor.fetchall()
                cols = [c[0] for c in cursor.description]
                results = [_row_to_dict(r, cols) for r in rows]
                return func.HttpResponse(json.dumps(results), status_code=200, mimetype="application/json")

        if req.method == "POST":
            try:
                payload = req.get_json()
            except ValueError:
                return func.HttpResponse(json.dumps({"error": "Invalid JSON"}), status_code=400, mimetype="application/json")
            product_id = payload.get("ProductId")
            product_name = payload.get("ProductName")
            category = payload.get("CategoryName")
            description = payload.get("Description", "")
            unit_price = payload.get("UnitPrice")
            if not product_name:
                return func.HttpResponse(json.dumps({"error": "Missing field: ProductName"}), status_code=400, mimetype="application/json")
            with _get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO ProductInfo (ProductId, ProductName, CategoryName, Description, UnitPrice) OUTPUT inserted.ProductRecordId VALUES (?, ?, ?, ?, ?)",
                    product_id, product_name, category, description, unit_price
                )
                inserted = cursor.fetchone()
                conn.commit()
                inserted_id = inserted[0] if inserted else None
            return func.HttpResponse(json.dumps({
                "ProductId": product_id,
                "ProductName": product_name,
                "CategoryName": category,
                "Description": description,
                "UnitPrice": unit_price
            }), status_code=201, mimetype="application/json")

        # python
        if req.method == "PUT":
            try:
                payload = req.get_json()
            except ValueError:
                return func.HttpResponse(json.dumps({"error": "Invalid JSON"}), status_code=400,
                                         mimetype="application/json")

            product_id = (
                    payload.get("ProductId")
                    or req.params.get("productid")
                    or req.params.get("product_id")
                    or req.params.get("id")
            )
            if not product_id:
                return func.HttpResponse(json.dumps({"error": "Missing field: ProductId"}), status_code=400,
                                         mimetype="application/json")

            # Only allow updating non-primary-key fields
            updates = []
            params = []
            for field in ("ProductName", "CategoryName", "Description", "UnitPrice"):
                if field in payload:
                    updates.append(f"{field} = ?")
                    params.append(payload.get(field))

            if not updates:
                return func.HttpResponse(json.dumps({"error": "No fields to update"}), status_code=400,
                                         mimetype="application/json")

            params.append(product_id)
            with _get_connection() as conn:
                cursor = conn.cursor()
                sql = f"UPDATE ProductInfo SET {', '.join(updates)} WHERE ProductId = ?"
                cursor.execute(sql, *params)
                if cursor.rowcount == 0:
                    conn.rollback()
                    return func.HttpResponse(json.dumps({"error": "Not found"}), status_code=404,
                                             mimetype="application/json")
                conn.commit()

            return func.HttpResponse(json.dumps({"ProductId": product_id, "updated": True}), status_code=200,
                                     mimetype="application/json")

        if req.method == "DELETE":
            product_id = (
                    req.params.get("productid")
                    or req.params.get("product_id")
                    or req.params.get("id")
            )
            if not product_id:
                try:
                    payload = req.get_json()
                    product_id = payload.get("ProductId")
                except ValueError:
                    pass

            if not product_id:
                return func.HttpResponse(json.dumps({"error": "Missing field: ProductId"}), status_code=400,
                                         mimetype="application/json")

            with _get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM ProductInfo WHERE ProductId = ?", product_id)
                if cursor.rowcount == 0:
                    conn.rollback()
                    return func.HttpResponse(json.dumps({"error": "Not found"}), status_code=404,
                                             mimetype="application/json")
                conn.commit()

            return func.HttpResponse(json.dumps({"ProductId": product_id, "deleted": True}), status_code=200,
                                     mimetype="application/json")

        return func.HttpResponse(status_code=405)

    except Exception as e:
        logging.exception("Database operation failed")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")