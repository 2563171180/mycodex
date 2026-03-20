from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
DB_PATH = DATA_DIR / "coldchain.db"
HOST = "0.0.0.0"
PORT = 8000


def ensure_database() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS popsicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                flavor TEXT NOT NULL,
                storage_zone TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity >= 0),
                unit_price REAL NOT NULL CHECK(unit_price >= 0),
                min_stock INTEGER NOT NULL CHECK(min_stock >= 0),
                supplier TEXT NOT NULL,
                production_date TEXT NOT NULL,
                expiry_date TEXT NOT NULL,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "flavor": row["flavor"],
        "storage_zone": row["storage_zone"],
        "quantity": row["quantity"],
        "unit_price": row["unit_price"],
        "min_stock": row["min_stock"],
        "supplier": row["supplier"],
        "production_date": row["production_date"],
        "expiry_date": row["expiry_date"],
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class ColdChainRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/popsicles":
            self.handle_list_popsicles(parse_qs(parsed.query))
            return
        if parsed.path == "/api/summary":
            self.handle_summary()
            return
        if parsed.path == "/health":
            self.send_json({"status": "ok", "timestamp": datetime.utcnow().isoformat()})
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        if self.path == "/api/popsicles":
            payload = self.read_json_body()
            self.handle_create_popsicle(payload)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def do_PUT(self) -> None:
        if self.path.startswith("/api/popsicles/"):
            popsicle_id = self.extract_id()
            payload = self.read_json_body()
            self.handle_update_popsicle(popsicle_id, payload)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def do_DELETE(self) -> None:
        if self.path.startswith("/api/popsicles/"):
            popsicle_id = self.extract_id()
            self.handle_delete_popsicle(popsicle_id)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def log_message(self, format: str, *args: Any) -> None:
        return

    def db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw_data = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw_data.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            self.send_json({"error": f"无效的 JSON：{exc.msg}"}, status=HTTPStatus.BAD_REQUEST)
            raise ValueError("invalid json") from exc

    def extract_id(self) -> int:
        try:
            return int(self.path.rstrip("/").split("/")[-1])
        except ValueError as exc:
            self.send_json({"error": "冰棒记录 ID 必须是数字。"}, status=HTTPStatus.BAD_REQUEST)
            raise ValueError("invalid id") from exc

    def validate_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        required_fields = [
            "name",
            "flavor",
            "storage_zone",
            "quantity",
            "unit_price",
            "min_stock",
            "supplier",
            "production_date",
            "expiry_date",
        ]
        missing = [field for field in required_fields if field not in payload or payload[field] in (None, "")]
        if missing:
            raise ValueError(f"以下字段不能为空：{', '.join(missing)}")

        quantity = int(payload["quantity"])
        min_stock = int(payload["min_stock"])
        unit_price = float(payload["unit_price"])
        if quantity < 0 or min_stock < 0 or unit_price < 0:
            raise ValueError("数量、最低库存和单价不能为负数。")

        production_date = datetime.strptime(payload["production_date"], "%Y-%m-%d").date()
        expiry_date = datetime.strptime(payload["expiry_date"], "%Y-%m-%d").date()
        if expiry_date <= production_date:
            raise ValueError("到期日期必须晚于生产日期。")

        return {
            "name": str(payload["name"]).strip(),
            "flavor": str(payload["flavor"]).strip(),
            "storage_zone": str(payload["storage_zone"]).strip(),
            "quantity": quantity,
            "unit_price": unit_price,
            "min_stock": min_stock,
            "supplier": str(payload["supplier"]).strip(),
            "production_date": production_date.isoformat(),
            "expiry_date": expiry_date.isoformat(),
            "notes": str(payload.get("notes", "")).strip(),
        }

    def handle_list_popsicles(self, query: dict[str, list[str]]) -> None:
        keyword = query.get("keyword", [""])[0].strip()
        zone = query.get("zone", [""])[0].strip()

        sql = "SELECT * FROM popsicles WHERE 1=1"
        params: list[Any] = []
        if keyword:
            sql += " AND (name LIKE ? OR flavor LIKE ? OR supplier LIKE ?)"
            fuzzy = f"%{keyword}%"
            params.extend([fuzzy, fuzzy, fuzzy])
        if zone:
            sql += " AND storage_zone = ?"
            params.append(zone)
        sql += " ORDER BY updated_at DESC, id DESC"

        with closing(self.db_connection()) as conn:
            items = [row_to_dict(row) for row in conn.execute(sql, params).fetchall()]
        self.send_json({"items": items})

    def handle_summary(self) -> None:
        today = datetime.utcnow().date().isoformat()
        with closing(self.db_connection()) as conn:
            summary_row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_skus,
                    COALESCE(SUM(quantity), 0) AS total_quantity,
                    COALESCE(SUM(quantity * unit_price), 0) AS inventory_value,
                    COALESCE(SUM(CASE WHEN quantity <= min_stock THEN 1 ELSE 0 END), 0) AS low_stock_count,
                    COALESCE(SUM(CASE WHEN expiry_date <= date(?, '+30 day') THEN 1 ELSE 0 END), 0) AS expiring_soon_count
                FROM popsicles
                """,
                (today,),
            ).fetchone()
            zones = [
                dict(row)
                for row in conn.execute(
                    "SELECT storage_zone, COUNT(*) AS sku_count, SUM(quantity) AS quantity FROM popsicles GROUP BY storage_zone ORDER BY quantity DESC"
                ).fetchall()
            ]

        self.send_json(
            {
                "summary": {
                    "total_skus": summary_row["total_skus"],
                    "total_quantity": summary_row["total_quantity"],
                    "inventory_value": round(summary_row["inventory_value"], 2),
                    "low_stock_count": summary_row["low_stock_count"],
                    "expiring_soon_count": summary_row["expiring_soon_count"],
                },
                "zones": zones,
            }
        )

    def handle_create_popsicle(self, payload: dict[str, Any]) -> None:
        try:
            data = self.validate_payload(payload)
        except (ValueError, TypeError) as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        now = datetime.utcnow().isoformat()
        with closing(self.db_connection()) as conn:
            cursor = conn.execute(
                """
                INSERT INTO popsicles (
                    name, flavor, storage_zone, quantity, unit_price, min_stock,
                    supplier, production_date, expiry_date, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["name"],
                    data["flavor"],
                    data["storage_zone"],
                    data["quantity"],
                    data["unit_price"],
                    data["min_stock"],
                    data["supplier"],
                    data["production_date"],
                    data["expiry_date"],
                    data["notes"],
                    now,
                    now,
                ),
            )
            conn.commit()
            item = conn.execute("SELECT * FROM popsicles WHERE id = ?", (cursor.lastrowid,)).fetchone()

        self.send_json({"item": row_to_dict(item)}, status=HTTPStatus.CREATED)

    def handle_update_popsicle(self, popsicle_id: int, payload: dict[str, Any]) -> None:
        try:
            data = self.validate_payload(payload)
        except (ValueError, TypeError) as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        now = datetime.utcnow().isoformat()
        with closing(self.db_connection()) as conn:
            existing = conn.execute("SELECT id FROM popsicles WHERE id = ?", (popsicle_id,)).fetchone()
            if not existing:
                self.send_json({"error": "未找到对应的冰棒记录。"}, status=HTTPStatus.NOT_FOUND)
                return

            conn.execute(
                """
                UPDATE popsicles
                SET name = ?, flavor = ?, storage_zone = ?, quantity = ?, unit_price = ?, min_stock = ?,
                    supplier = ?, production_date = ?, expiry_date = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    data["name"],
                    data["flavor"],
                    data["storage_zone"],
                    data["quantity"],
                    data["unit_price"],
                    data["min_stock"],
                    data["supplier"],
                    data["production_date"],
                    data["expiry_date"],
                    data["notes"],
                    now,
                    popsicle_id,
                ),
            )
            conn.commit()
            item = conn.execute("SELECT * FROM popsicles WHERE id = ?", (popsicle_id,)).fetchone()

        self.send_json({"item": row_to_dict(item)})

    def handle_delete_popsicle(self, popsicle_id: int) -> None:
        with closing(self.db_connection()) as conn:
            cursor = conn.execute("DELETE FROM popsicles WHERE id = ?", (popsicle_id,))
            conn.commit()
        if cursor.rowcount == 0:
            self.send_json({"error": "未找到对应的冰棒记录。"}, status=HTTPStatus.NOT_FOUND)
            return
        self.send_json({"message": "删除成功。"})

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ensure_database()
    server = ThreadingHTTPServer((HOST, PORT), ColdChainRequestHandler)
    print(f"冷链冰棒管理系统已启动：http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止。")
    finally:
        server.server_close()
