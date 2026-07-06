import os
print(os.getcwd())

from flask import (
    Flask, flash, render_template, request,
    redirect, session, url_for, jsonify, g
)
from flask_bcrypt import Bcrypt
from datetime import timedelta
import pymysql
import random
from urllib.parse import quote
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from translations import translations

# ================= LOAD ENV =================

load_dotenv()

# ================= APP CONFIG =================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static/images")

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

bcrypt = Bcrypt(app)

app.permanent_session_lifetime = timedelta(days=7)

# ================= DATABASE CONFIG =================
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "4000"))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
# ================= MYSQL CONNECTION =================

def get_db():
    if "db" not in g:
        g.db = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            ssl={"ssl": {}}
        )
    return g.db

# ================= CLOSE CONNECTION =================

@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()

# ================= CHECK USERS =================

def check_users():

    conn = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

    cur = conn.cursor()

    cur.execute("SELECT * FROM users")

    users = cur.fetchall()

    print("\n----- USERS -----")

    for user in users:
        print(
            f"ID: {user['id']} | "
            f"Email: {user['email']} | "
            f"Role: {user['role']} | "
            f"Name: {user['name']}"
        )

    print("-----------------\n")

    cur.close()
    conn.close()

# ================= CREATE TABLES =================

def init_db():
    conn = pymysql.connect(
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    cursorclass=pymysql.cursors.DictCursor,
    ssl={"ssl": {}}
)
    cur = conn.cursor()

    

    # ---------------- USERS ----------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role VARCHAR(50) NOT NULL,
        mobile VARCHAR(20)
    )
    """)

    # ---------------- SUPPLIERS ----------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS suppliers(
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        name VARCHAR(255),
        latitude DOUBLE DEFAULT 18.5204,
        longitude DOUBLE DEFAULT 73.8567
    )
    """)

    # ---------------- PRODUCTS ----------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS products(
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        price DECIMAL(10,2) DEFAULT 0,
        stock INT DEFAULT 0,
        image VARCHAR(255),
        category VARCHAR(100),
        supplier_id INT DEFAULT 0
    )
        """)
    # ---------------- ORDERS ----------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders(
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    user_name VARCHAR(255),
    supplier_id INT DEFAULT 0,
    product_name VARCHAR(255) NOT NULL,
    price DECIMAL(10,2) DEFAULT 0,
    quantity INT DEFAULT 1,
    total DECIMAL(10,2) DEFAULT 0,
    status VARCHAR(50) DEFAULT 'Pending',
    payment_method VARCHAR(100),
    location TEXT,
    mobile VARCHAR(20),
    payment_id VARCHAR(255),
    payment_settled TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    order_id VARCHAR(255) UNIQUE
)
    """)
   
    # ---------------- DISEASES ----------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS diseases(
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255),
        image VARCHAR(255),
        fertilizer_id INT
    )
    """)

    # ---------------- FERTILIZERS ----------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS fertilizers(
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        price DECIMAL(10,2) DEFAULT 0,
        stock INT DEFAULT 0,
        image VARCHAR(255)
    )
    """)

    # ---------------- FEEDBACKS ----------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS feedbacks(
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        product VARCHAR(255),
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ---------------- DEFAULT PRODUCTS ----------------

    products_list = [
        ("Apple Plant", 120, 50, "appleplant.png", "plant", 0),
        ("Banana Plant", 80, 40, "banana.png", "plant", 0),
        ("Sunflower Seeds", 60, 100, "sunflower.png", "seed", 0),
        ("Wheat Seed", 149, 100, "wheat.png", "seed", 0)
    ]

    for p in products_list:

        cur.execute(
            "SELECT id FROM products WHERE name=%s",
            (p[0],)
        )

        if not cur.fetchone():

            cur.execute("""
            INSERT INTO products
            (name, price, stock, image, category, supplier_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """, p)

    conn.commit()
    conn.close()

    print("✅ MySQL Database Initialized")
    # ================= TRANSLATIONS =================

@app.context_processor
def inject_translations():
    lang = session.get("lang", "en")
    return {
        "texts": translations.get(
            lang,
            translations["en"]
        )
    }


# ================= SESSION SETUP =================

_got_first_request = False

@app.before_request
def before_request():

    global _got_first_request

    session.permanent = True

    if not _got_first_request:
        print("✅ Running first-time setup...")
        _got_first_request = True


# ================= ROOT ROUTE =================

@app.route("/")
def index():

    if "user_id" not in session:
        return redirect(url_for("login"))

    role = session.get("role")

    if role == "customer":
        return redirect("/home")

    elif role == "admin":
        return redirect("/admin")

    elif role == "supplier":
        return redirect("/supplier")

    return "Access Denied", 403


# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM users WHERE email=%s",
            (email,)
        )

        user = cur.fetchone()

        if not user:
            return "Account not found! ❌", 404

        if not bcrypt.check_password_hash(
            user["password"],
            password
        ):
            return "Invalid Password! ❌", 401

        session.clear()

        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["username"] = user["name"]
        session["mobile"] = user.get("mobile")

        if user["role"] == "admin":
            return redirect("/admin")

        elif user["role"] == "supplier":
            return redirect("/supplier")

        return redirect("/home")

    return render_template("Sign_Up.html")

@app.route("/signup", methods=["POST"])
def signup():

    name = request.form.get("name")
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password")
    mobile = request.form.get("mobile")
    role = request.form.get("role")

    hashed_password = bcrypt.generate_password_hash(
        password
    ).decode("utf-8")

    conn = get_db()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO users
            (name, email, password, role, mobile)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            name,
            email,
            hashed_password,
            role,
            mobile
        ))

        conn.commit()

        return redirect("/login")

    except pymysql.err.IntegrityError:

        return "Email already exists ❌"

# ================= CUSTOMER HOME =================

@app.route("/home")
def home():

    if "user_id" not in session:
        return redirect("/login")

    if session.get("role") != "customer":
        return "Access Denied", 403

    lang = session.get("lang", "en")

    return render_template(
        "Home.html",
        username=session.get("username"),
        texts=translations.get(
            lang,
            translations["en"]
        )
    )


# ================= LANGUAGE =================

@app.route("/set_language/<lang_code>")
def set_language(lang_code):

    if lang_code in translations:
        session["lang"] = lang_code

    return redirect(
        request.referrer or url_for("home")
    )


# ================= SEARCH =================
@app.route("/search")
def search():

    if "user_id" not in session:
        return redirect("/login")

    query = request.args.get("query", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    if query:

        search = "%" + query + "%"

        cursor.execute("""
            SELECT *
            FROM products
            WHERE
                name LIKE %s
                OR category LIKE %s
            ORDER BY id DESC
        """, (search, search))

        results = cursor.fetchall()

    else:
        results = []

    cursor.close()
    conn.close()

    return render_template(
        "search_results.html",
        query=query,
        results=results
    )
    # ================= PLANTS =================

@app.route("/plants")
def plants_page():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.*,
            u.name AS supplier_name
        FROM products p
        LEFT JOIN users u
            ON p.supplier_id = u.id
        WHERE p.category='plant'
    """)

    plants = cur.fetchall()

    return render_template(
        "plants.html",
        plants=plants
    )


# ================= SEEDS =================

@app.route("/seeds")
def seeds_page():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.*,
            u.name AS supplier_name
        FROM products p
        LEFT JOIN users u
            ON p.supplier_id = u.id
        WHERE p.category='seed'
    """)

    seeds = cur.fetchall()

    return render_template(
        "Seeds.html",
        seeds=seeds
    )
# --------------------------------FERTILIZERS -------------------------------------#
# ================= FERTILIZERS =================

@app.route("/fertilizers")
def fertilizers_page():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM fertilizers")

    fertilizers = cur.fetchall()

    return render_template(
        "fertilizers.html",
        fertilizers=fertilizers
    )


# ================= DISEASES =================

@app.route("/diseases")
def diseases_page():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM diseases")

    diseases = cur.fetchall()

    return render_template(
        "diseases.html",
        diseases=diseases
    )


@app.route("/flowers")
def flowers_page():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.*,
            u.name AS supplier_name
        FROM products p
        LEFT JOIN users u
            ON p.supplier_id = u.id
        WHERE p.category='flower'
    """)

    flowers = cur.fetchall()

    return render_template(
        "flowers.html",
        flowers=flowers
    )
@app.route("/bonsai")
def bonsai_page():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.*,
            u.name AS supplier_name
        FROM products p
        LEFT JOIN users u
            ON p.supplier_id = u.id
        WHERE p.category='bonsai'
    """)

    plants = cur.fetchall()

    return render_template(
        "bonsai.html",
        plants=plants
    )
@app.route("/fruit_plants")
def fruit_plants_page():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.*,
            u.name AS supplier_name
        FROM products p
        LEFT JOIN users u
            ON p.supplier_id = u.id
        WHERE p.category='fruit_plants'
    """)

    fruit_plants = cur.fetchall()

    return render_template(
        "fruit_plants.html",
        fruit_plants=fruit_plants
    )
@app.route("/pots")
def pots_page():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.*,
            u.name AS supplier_name
        FROM products p
        LEFT JOIN users u
            ON p.supplier_id = u.id
        WHERE p.category='pots'
    """)

    pots = cur.fetchall()

    return render_template(
        "pots.html",
        pots=pots
    )
@app.route("/soil")
def soil_page():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.*,
            u.name AS supplier_name
        FROM products p
        LEFT JOIN users u
            ON p.supplier_id = u.id
        WHERE p.category='soil'
    """)

    soil = cur.fetchall()

    return render_template(
        "soil.html",
        soil=soil
    )

@app.route("/vegetable_seeds")
def vegetable_seeds_page():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.*,
            u.name AS supplier_name
        FROM products p
        LEFT JOIN users u
            ON p.supplier_id = u.id
        WHERE p.category='vegetable_seeds'
    """)

    vegetable_seeds = cur.fetchall()

    return render_template(
        "vegetable_seeds.html",
        vegetable_seeds=vegetable_seeds
    )
@app.route("/indoor_plants")
def indoor_plants_page():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.*,
            u.name AS supplier_name
        FROM products p
        LEFT JOIN users u
            ON p.supplier_id = u.id
        WHERE p.category='indoor_plants'
    """)

    indoor_plants = cur.fetchall()

    return render_template(
        "indoor_plants.html",
        indoor_plants=indoor_plants
    )
@app.route("/outdoor_plants")
def outdoor_plants_page():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.*,
            u.name AS supplier_name
        FROM products p
        LEFT JOIN users u
            ON p.supplier_id = u.id
        WHERE p.category='outdoor_plants'
    """)

    outdoor_plants = cur.fetchall()

    return render_template(
        "outdoor_plants.html",
        outdoor_plants=outdoor_plants
    )

@app.route("/gifts")
def gifts_page():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.*,
            u.name AS supplier_name
        FROM products p
        LEFT JOIN users u
            ON p.supplier_id = u.id
        WHERE p.category='gifts'
    """)

    gifts = cur.fetchall()

    return render_template(
        "gifts.html",
        gifts=gifts
    )
@app.route("/herbal_plants")
def herbal_plants_page():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.*,
            u.name AS supplier_name
        FROM products p
        LEFT JOIN users u
            ON p.supplier_id = u.id
        WHERE p.category='herbal_plants'
    """)

    herbal_plants = cur.fetchall()

    return render_template(
        "herbal_plants.html",
        herbal_plants=herbal_plants
    )    
@app.route("/succulents")
def succulents_page():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.*,
            u.name AS supplier_name
        FROM products p
        LEFT JOIN users u
            ON p.supplier_id = u.id
        WHERE p.category='succulents'
    """)

    succulents = cur.fetchall()

    return render_template(
        "succulents.html",
        succulents=succulents
    )    
# ================= FERTILIZER BY DISEASE =================

@app.route("/fertilizer/<int:id>")
def fertilizer_by_disease(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT f.*
        FROM diseases d
        JOIN fertilizers f
            ON d.fertilizer_id = f.id
        WHERE d.id=%s
    """, (id,))

    fertilizer = cur.fetchone()

    return render_template(
        "fertilizer_view.html",
        fertilizer=fertilizer
    )


# ================= ORDERS =================

@app.route("/orders")
def orders_page():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM orders
        WHERE user_id=%s
        ORDER BY created_at DESC
    """, (session["user_id"],))

    orders = cur.fetchall()

    return render_template(
        "Orderss.html",
        orders=orders
    )


# ================= ORDER HISTORY =================

# ================= ORDER HISTORY =================

@app.route("/order_history")
def order_history():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM orders
        WHERE user_id=%s
        ORDER BY id DESC
    """, (session["user_id"],))

    orders = cur.fetchall()

    return render_template(
        "order_history.html",
        orders=orders
    )


# ================= CONFIRM ORDER =================
@app.route("/confirm_order", methods=["POST"])
def confirm_order():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Login required"
        })

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "No data received"
        })

    cart = data.get("cart", [])
    location = data.get("location", "")

    user_id = session.get("user_id")
    user_name = session.get("username")
    mobile = session.get("mobile")

    conn = get_db()
    cur = conn.cursor()

    try:

        for item in cart:

            cur.execute(
                "SELECT supplier_id FROM products WHERE name=%s",
                (item["name"],)
            )

            res = cur.fetchone()

            supplier_id = (
                res["supplier_id"]
                if res and res["supplier_id"]
                else 1
            )

            total = float(item["price"]) * int(item["quantity"])

            cur.execute("""
                INSERT INTO orders(
                    user_id,
                    user_name,
                    mobile,
                    supplier_id,
                    product_name,
                    price,
                    quantity,
                    total,
                    location,
                    status
                )
                VALUES(
                    %s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s
                )
            """, (
                user_id,
                user_name,
                mobile,
                supplier_id,
                item["name"],
                item["price"],
                item["quantity"],
                total,
                location,
                "Pending"
            ))

            cur.execute("""
                UPDATE products
                SET stock = stock - %s
                WHERE name=%s
            """, (
                item["quantity"],
                item["name"]
            ))

        conn.commit()

        return jsonify({
            "success": True
        })

    except Exception as e:

        conn.rollback()

        print("❌ Order Error:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        })



@app.route("/remove_order/<int:order_id>", methods=["POST"])
def remove_order(order_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM products
        WHERE id=%s
        AND user_id=%s
        AND status='Pending'
    """, (
        order_id,
        session["user_id"]
    ))

    conn.commit()

    return redirect("/orders")


# ================= BUY NOW =================

@app.route("/buy_now/<int:order_id>", methods=["POST"])
def buy_now(order_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM orders
        WHERE id=%s
        AND user_id=%s
    """, (
        order_id,
        session["user_id"]
    ))

    order = cur.fetchone()

    if not order:
        return "Order not found ❌"

    return render_template(
        "Payments.html",
        orders=[order]
    )
    # ================= FEEDBACK =================

@app.route("/feedback", methods=["GET", "POST"])
def feedback():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT product_name
        FROM orders
        WHERE user_id=%s
    """, (user_id,))

    products = [
        row["product_name"]
        for row in cur.fetchall()
    ]

    if request.method == "POST":

        product = request.form["product"]
        message = request.form["message"]

        cur.execute("""
            INSERT INTO feedbacks
            (user_id, product, message)
            VALUES (%s,%s,%s)
        """, (
            user_id,
            product,
            message
        ))

        conn.commit()

        return redirect(url_for("feedback"))

    return render_template(
        "Feedbacks.html",
        products=products
    )


# ================= ADMIN FEEDBACKS =================

@app.route("/admin/feedbacks")
def admin_feedbacks():

    if session.get("role") != "admin":
        return "Access Denied", 403

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            feedbacks.id,
            users.name,
            feedbacks.product,
            feedbacks.message,
            feedbacks.created_at
        FROM feedbacks
        JOIN users
            ON feedbacks.user_id = users.id
        ORDER BY feedbacks.id DESC
    """)

    feedbacks = cur.fetchall()

    return render_template(
        "admin_feedbacks.html",
        feedbacks=feedbacks
    )


# ================= ADMIN DASHBOARD =================

@app.route("/admin")
def admin_dashboard():

    if (
        "user_id" not in session or
        session.get("role") != "admin"
    ):
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    # Total Orders
    cur.execute("SELECT COUNT(*) AS total FROM orders")
    total_orders = cur.fetchone()["total"] or 0

    # Revenue
    cur.execute("SELECT SUM(total) AS revenue FROM orders")
    revenue_row = cur.fetchone()
    total_revenue = revenue_row["revenue"] or 0

    # Customers
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM users
        WHERE role='customer'
    """)
    total_customers = cur.fetchone()["total"] or 0

    # Products
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM products
    """)
    total_products = cur.fetchone()["total"] or 0

    # Recent Orders
    cur.execute("""
        SELECT
            o.*,
            u.name AS customer_name,
            u.mobile,
            u.role
        FROM orders o
        LEFT JOIN users u
            ON o.user_id = u.id
        ORDER BY o.id DESC
        LIMIT 10
    """)

    recent_orders = cur.fetchall()

    # Unsettled Orders
    cur.execute("""
        SELECT
            o.id,
            o.product_name,
            o.total,
            COALESCE(
                s.name,
                'Unknown'
            ) AS supplier_name
        FROM orders o
        LEFT JOIN users s
            ON o.supplier_id = s.id
        WHERE o.status='Delivered'
        AND (
            o.payment_settled=0
            OR o.payment_settled IS NULL
        )
    """)

    unsettled_orders = cur.fetchall()

    return render_template(
        "admin.html",
        total_products=total_products,
        total_orders=total_orders,
        total_customers=total_customers,
        total_revenue=total_revenue,
        orders=recent_orders,
        unsettled_orders=unsettled_orders,
        active="dashboard"
    )


# ================= PAYMENT PAGE =================

@app.route("/payment/<int:order_id>")
def payment_page(order_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM orders
        WHERE id=%s
    """, (order_id,))

    order = cur.fetchone()

    if not order:
        return "Order not found ❌", 404

    return render_template(
        "Payments.html",
        order=order
    )
# ================= SUPPLIER DASHBOARD =================

@app.route("/supplier")
def supplier_dashboard():

    if (
        "user_id" not in session or
        session.get("role") != "supplier"
    ):
        return redirect("/login")

    supplier_id = session["user_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            o.*,
            u.name AS user_name,
            u.mobile AS user_mobile
        FROM orders o
        LEFT JOIN users u
            ON o.user_id = u.id
        WHERE
            o.supplier_id=%s
            OR (o.supplier_id IS NULL AND o.status='Placed')
            OR (o.supplier_id=0 AND o.status='Placed')
        ORDER BY o.id DESC
    """, (supplier_id,))

    orders = cur.fetchall()

    cur.execute("""
        SELECT *
        FROM products
        WHERE supplier_id=%s
        ORDER BY id DESC
    """, (supplier_id,))

    products = cur.fetchall()

    return render_template(
        "supplier.html",
        orders=orders,
        products=products
    )


# ================= CONTACT =================

@app.route("/contact")
def contact_view():

    map_url = (
        "https://www.google.com/maps/embed?"
        "pb=!1m18!1m12!1m3!1d3781.332306353982!"
        "2d73.7661595751936!3d18.60411888251214"
    )

    return render_template(
        "contact.html",
        map_url=map_url
    )


# ================= SUPPLIER ACTION =================

@app.route("/supplier_action/<int:order_id>", methods=["POST"])
def supplier_action(order_id):

    if (
        "user_id" not in session or
        session.get("role") != "supplier"
    ):
        return redirect("/login")

    action = request.form.get("action")

    conn = get_db()
    cur = conn.cursor()

    if action == "accept":

        cur.execute("""
            UPDATE orders
            SET supplier_id=%s,
                status='Accepted'
            WHERE id=%s
        """, (
            session["user_id"],
            order_id
        ))

        conn.commit()

        return redirect("/supplier")

    elif action == "out_for_delivery":
        new_status = "On the Way"

    elif action == "deliver":
        new_status = "Delivered"

    elif action == "reject":
        new_status = "Rejected"

    else:
        return redirect("/supplier")

    cur.execute("""
        UPDATE orders
        SET status=%s
        WHERE id=%s
    """, (
        new_status,
        order_id
    ))

    conn.commit()

    return redirect("/supplier")


# ================= DELETE PRODUCT =================

@app.route("/delete_product/<int:product_id>")
def delete_product(product_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM products
        WHERE product_id=%s
        AND supplier_id=%s
    """, (
        product_id,
        session["user_id"]
    ))

    conn.commit()

    return redirect("/supplier")

@app.route("/admin/delete_product/<int:product_id>", methods=["POST"])
def admin_delete_product(product_id):

    if (
        "user_id" not in session or
        session.get("role") != "admin"
    ):
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute(
            "DELETE FROM products WHERE id=%s",
            (product_id,)
        )

        conn.commit()

    except Exception as e:
        print("Delete Error:", e)

    return redirect("/admin/products")
# ================= ADD PRODUCT PAGE =================

@app.route("/supplier/add_product_page")
def add_product_page():

    if (
        "user_id" not in session or
        session.get("role") != "supplier"
    ):
        return redirect("/login")

    return render_template("add_product.html")


# ================= ADD PRODUCT =================
@app.route("/admin/suppliers")
def admin_suppliers():

    if session.get("role") != "admin":
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM users
        WHERE role='supplier'
        ORDER BY id DESC
    """)

    suppliers = cur.fetchall()

    return render_template(
        "admin_suppliers.html",
        suppliers=suppliers
    )
@app.route("/admin/supplier/<int:supplier_id>")
def supplier_details(supplier_id):

    if session.get("role") != "admin":
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    # Supplier Info
    cur.execute("""
        SELECT *
        FROM users
        WHERE id=%s AND role='supplier'
    """, (supplier_id,))
    supplier = cur.fetchone()

    # Products Added By Supplier
    cur.execute("""
        SELECT *
        FROM products
        WHERE supplier_id=%s
    """, (supplier_id,))
    products = cur.fetchall()

    # Orders For Supplier
    cur.execute("""
        SELECT *
        FROM orders
        WHERE supplier_id=%s
        ORDER BY created_at DESC
    """, (supplier_id,))
    orders = cur.fetchall()

    # Statistics
    cur.execute("""
        SELECT
            COUNT(*) total_orders,
            COALESCE(SUM(total),0) total_sales
        FROM orders
        WHERE supplier_id=%s
    """, (supplier_id,))
    stats = cur.fetchone()

    return render_template(
        "supplier_details.html",
        supplier=supplier,
        products=products,
        orders=orders,
        stats=stats
    )
@app.route("/supplier/add_product", methods=["POST"])
def supplier_add_product():

    if "user_id" not in session:
        return redirect("/login")

    print("FORM:", request.form)

    name = request.form.get("product_name")
    price = request.form.get("price")
    stock = request.form.get("stock")
    category = request.form.get("category")

    print("Name =", name)
    print("Price =", price)
    print("Stock =", stock)
    print("Category =", category)

    if not name:
        return "Product Name Missing", 400

    image = request.files.get("image")

    image_name = "default_plant.png"

    if image and image.filename:
        image_name = secure_filename(image.filename)
        image.save(os.path.join(app.config["UPLOAD_FOLDER"], image_name))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO products
        (
            name,
            price,
            stock,
            image,
            category,
            supplier_id
        )
        VALUES
        (%s,%s,%s,%s,%s,%s)
    """,(
        name,
        price,
        stock,
        image_name,
        category,
        session["user_id"]
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/supplier")

# ================= UPDATE ORDER =================

@app.route("/update_order/<int:id>/<status>")
def update_order(id, status):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE orders
        SET status=%s
        WHERE id=%s
    """, (
        status,
        id
    ))

    conn.commit()

    return redirect("/supplier")


# ================= UPDATE STATUS (ADMIN) =================

@app.route("/update_status/<int:order_id>", methods=["POST"])
def update_status(order_id):

    if session.get("role") != "admin":
        return "Access Denied", 403

    status = request.form.get("status")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE orders
        SET status=%s
        WHERE id=%s
    """, (
        status,
        order_id
    ))

    conn.commit()

    return redirect("/admin/orders")


# ================= CREATE ADMIN =================

@app.route("/create_admin")
def create_admin_route():

    conn = get_db()
    cur = conn.cursor()

    hashed_pw = bcrypt.generate_password_hash(
        "admin123"
    ).decode("utf-8")

    try:

        cur.execute("""
            INSERT INTO users(
                name,
                email,
                password,
                role,
                mobile
            )
            VALUES(
                %s,%s,%s,%s,%s
            )
        """, (
            "Admin User",
            "admin@gmail.com",
            hashed_pw,
            "admin",
            "9999999999"
        ))

        conn.commit()

        return """
        ✅ Admin Created<br>
        Email: admin@gmail.com<br>
        Password: admin123
        """

    except Exception as e:

        return f"""
        ❌ Admin already exists
        <br><br>
        Error: {str(e)}
        """


# ================= CREATE SUPPLIER =================

@app.route("/create_supplier")
def create_supplier():

    conn = get_db()
    cur = conn.cursor()

    password = bcrypt.generate_password_hash(
        "supplier123"
    ).decode("utf-8")

    try:

        cur.execute("""
            INSERT INTO users(
                name,
                email,
                password,
                role
            )
            VALUES(
                %s,%s,%s,%s
            )
        """, (
            "Supplier",
            "supplier@gmail.com",
            password,
            "supplier"
        ))

        conn.commit()

        return """
        ✅ Supplier Created<br>
        Email: supplier@gmail.com<br>
        Password: supplier123
        """

    except Exception:
        return "Supplier already exists ✅"
# --------------------------------LOGOUT-------------------------------------#
# ================= LOGOUT =================

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ================= VERIFY ORDER =================

@app.route("/verify_order/<mobile>")
def verify_order(mobile):

    message = "Your order is confirmed ✅ Thank you for shopping with us!"

    encoded_message = quote(message)

    whatsapp_url = (
        f"https://wa.me/91{mobile}?text={encoded_message}"
    )

    return redirect(whatsapp_url)


# ================= ADMIN ORDERS =================

@app.route("/admin/orders")
def admin_orders():

    if (
        "user_id" not in session or
        session.get("role") != "admin"
    ):
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM orders
        ORDER BY id DESC
    """)

    orders = cur.fetchall()

    return render_template(
        "admin_orders.html",
        orders=orders
    )


# ================= ADMIN ADD PRODUCT =================

@app.route("/admin/add_product", methods=["GET", "POST"])
def admin_add_product():

    if (
        "user_id" not in session or
        session.get("role") != "admin"
    ):
        flash(
            "Unauthorized access!",
            "danger"
        )
        return redirect("/login")

    if request.method == "POST":

        name = request.form.get("name")
        price = request.form.get("price")
        stock = request.form.get("stock")
        category = request.form.get("category")

        file = request.files.get("image")

        filename = "default_plant.png"

        if file and file.filename:

            filename = secure_filename(
                file.filename
            )

            if not os.path.exists(
                app.config["UPLOAD_FOLDER"]
            ):
                os.makedirs(
                    app.config["UPLOAD_FOLDER"]
                )

            file.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )

        try:

            conn = get_db()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO products(
                    name,
                    price,
                    stock,
                    image,
                    category,
                    supplier_id
                )
                VALUES(
                    %s,%s,%s,%s,%s,%s
                )
            """, (
                name,
                price,
                stock,
                filename,
                category.lower(),
                session["user_id"]
            ))

            conn.commit()

            flash(
                "Product Added Successfully! ✅",
                "success"
            )

            return redirect(
                "/admin/products"
            )

        except Exception as e:

            print(
                "Product Add Error:",
                e
            )

            flash(
                "Database Error! ❌",
                "danger"
            )

            return redirect(
                "/admin/add_product"
            )

    return render_template(
        "admin_add_product.html",
        active="add_product"
    )


# ================= MANAGE PRODUCTS =================

@app.route("/admin/products")
def manage_products():

    if (
        "user_id" not in session or
        session.get("role") != "admin"
    ):
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM products
        ORDER BY id DESC
    """)

    products = cur.fetchall()

    return render_template(
        "admin_products.html",
        products=products
    )

    # ================= ADMIN CUSTOMERS =================

@app.route("/admin/customers")
def admin_customers():

    if (
        "user_id" not in session or
        session.get("role") != "admin"
    ):
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            name,
            email,
            mobile
        FROM users
        WHERE role='customer'
        ORDER BY id DESC
    """)

    customers = cur.fetchall()

    return render_template(
        "admin_customers.html",
        customers=customers
    )

@app.route("/admin/customer/<int:customer_id>")
def customer_details(customer_id):

    if session.get("role") != "admin":
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    # Customer Info
    cur.execute("""
        SELECT id, name, email, mobile
        FROM users
        WHERE id=%s
    """, (customer_id,))
    customer = cur.fetchone()

    # Customer Orders
    cur.execute("""
        SELECT *
        FROM orders
        WHERE user_id=%s
        ORDER BY created_at DESC
    """, (customer_id,))
    orders = cur.fetchall()

    # Stats
    cur.execute("""
        SELECT
            COUNT(*) as total_orders,
            COALESCE(SUM(total),0) as total_spent
        FROM orders
        WHERE user_id=%s
    """, (customer_id,))
    stats = cur.fetchone()

    return render_template(
        "customer_details.html",
        customer=customer,
        orders=orders,
        stats=stats
    )
    # ================= ADMIN REPORTS =================

@app.route("/admin/reports")
def admin_reports():

    if (
        "user_id" not in session or
        session.get("role") != "admin"
    ):
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT SUM(total) AS revenue
        FROM orders
    """)

    row = cur.fetchone()

    revenue = (
        row["revenue"]
        if row and row["revenue"]
        else 0
    )

    return render_template(
        "admin_reports.html",
        revenue=revenue
    )


# ================= SUCCESS =================

@app.route("/success")
def success():
    return "Payment Successful! ✅"


# ================= UPDATE LOCATION =================

@app.route("/update_location", methods=["POST"])
def update_location():

    if "user_id" not in session:
        return "Unauthorized", 401

    data = request.get_json()

    lat = data.get("lat")
    lng = data.get("lng")

    supplier_id = session.get("user_id")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE suppliers
        SET latitude=%s,
            longitude=%s
        WHERE user_id=%s
    """, (
        lat,
        lng,
        supplier_id
    ))

    conn.commit()

    return "OK"


# ================= PLACE ORDER =================
@app.route("/place_order", methods=["POST"])
def place_order():
    try:
        if "user_id" not in session:
            return jsonify({"success": False, "message": "Login Required"}), 401

        data = request.get_json()

        if not data:
            return jsonify({"success": False, "message": "No JSON Data"}), 400

        payment_method = data.get("payment_method")
        user_id = session["user_id"]

        conn = get_db()
        cur = conn.cursor()

        sql = """
            UPDATE orders
            SET payment_method=%s,
                status='Completed'
            WHERE user_id=%s
              AND status='Pending'
            ORDER BY id DESC
            LIMIT 1
        """

        cur.execute(sql, (payment_method, user_id))
        conn.commit()

        return jsonify({"success": True})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500
    # ================= PAYMENTS =================

@app.route("/payments")
def payments():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, total
        FROM orders
        WHERE user_id=%s AND status='Pending'
        ORDER BY id DESC
        LIMIT 1
    """, (user_id,))

    order = cur.fetchone()

    if not order:
        return render_template(
            "payments.html",
            order_items=[],
            total_amount=0,
            order_id=None
        )

    order_id = order["id"]
    total_amount = order["total"]

    # since order_items table does NOT exist
    items = []

    return render_template(
        "payments.html",
        order_items=items,
        total_amount=total_amount,
        order_id=order_id
    )
    # ================= GET SUPPLIER LOCATION =================

@app.route('/get_supplier_location/<int:order_id>')
def get_supplier_location(order_id):

    location_data = {
        "lat": 18.5204,
        "lng": 73.8567,
        "status": "On the Way"
    }

    return jsonify(location_data)


# ================= PAYMENT HISTORY =================
@app.route("/payment_history")
def payment_history():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    # Current order items
    cur.execute("""
        SELECT product_name, quantity
        FROM orders
        WHERE user_id=%s
        ORDER BY id DESC
    """, (session["user_id"],))
    order_items = cur.fetchall()

    # Total amount
    cur.execute("""
        SELECT SUM(total) AS total
        FROM orders
        WHERE user_id=%s
    """, (session["user_id"],))
    row = cur.fetchone()
    total_amount = row["total"] if row["total"] else 0

    # Order history
    cur.execute("""
        SELECT
            id,
            product_name,
            quantity,
            price,
            total,
            status,
            payment_method
        FROM orders
        WHERE user_id=%s
        ORDER BY id DESC
    """, (session["user_id"],))
    orders = cur.fetchall()

    cur.close()

    return render_template(
        "payments.html",
        order_items=order_items,
        total_amount=total_amount,
        payment_history=orders
    )
# ================= UPDATE SUPPLIER LOCATION =================

@app.route("/update_supplier_location", methods=["POST"])
def update_supplier_location():

    supplier_id = session.get("user_id")

    if not supplier_id:
        return jsonify({
            "status": "error",
            "message": "Not logged in"
        }), 401

    data = request.get_json()

    lat = data.get("latitude")
    lng = data.get("longitude")

    try:

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            UPDATE suppliers
            SET latitude=%s,
                longitude=%s
            WHERE user_id=%s
        """, (
            lat,
            lng,
            supplier_id
        ))

        conn.commit()

        return jsonify({
            "status": "success"
        })

    except Exception as e:

        print(
            "Location Update Error:",
            e
        )

        return jsonify({
            "status": "error"
        }), 500


# ================= INVENTORY =================

@app.route("/admin/inventory")
def inventory():

    if (
        "user_id" not in session or
        session.get("role") != "admin"
    ):
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM products
        ORDER BY id DESC
    """)

    products = cur.fetchall()

    return render_template(
        "inventory.html",
        products=products
    )


# ================= EDIT PRODUCT =================

@app.route('/edit_product/<int:id>', methods=['GET', 'POST'])
def edit_product(id):

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":

        name = request.form["name"]
        price = request.form["price"]
        stock = request.form["stock"]
        category = request.form["category"]

        cur.execute("""
            UPDATE products
            SET
                name=%s,
                price=%s,
                stock=%s,
                category=%s
            WHERE id=%s
        """, (
            name,
            price,
            stock,
            category,
            id
        ))

        conn.commit()

        return redirect(
            url_for("inventory")
        )

    cur.execute("""
        SELECT *
        FROM products
        WHERE id=%s
    """, (id,))

    product = cur.fetchone()

    return render_template(
        "edit_product.html",
        product=product
    )


# ================= MAIN =================
if __name__ == "__main__":
    
    print("Initializing Database...")
    init_db()
with app.app_context():
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)