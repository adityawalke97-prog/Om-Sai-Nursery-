import os
from unittest.mock import DEFAULT
from flask import Flask, flash, render_template, request, redirect, session, url_for, jsonify, g
from flask_bcrypt import Bcrypt
from datetime import timedelta
import sqlite3
import random
from urllib.parse import quote
from werkzeug.utils import secure_filename
from translations import translations

# ----------------- APP & DB CONFIG -----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/images')

# --- Ye aapke app.py ke upar ke hisse mein hoga ---
app = Flask(__name__)
app.secret_key = "supersecretkey"

# ✅ YE WALI LINES ADD KAREIN:

# -----------------------------------------------app.secret_key = "supersecretkey"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
bcrypt = Bcrypt(app)
app.permanent_session_lifetime = timedelta(days=7)

def check_users():
    conn = sqlite3.connect('nursery.db') # Aapki db file ka naam yahan likhein
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    users = cur.execute("SELECT * FROM users").fetchall()
    
    print("\n--- Database mein ye Users hain ---")
    for user in users:
        print(f"ID: {user['id']} | Email: {user['email']} | Role: {user['role']} | Name: {user['name']}")
    print("------------------------------------\n")
    conn.close()
def get_db():
    if 'db' not in g:
        # Dono lines ko merge karke sahi path aur row_factory set karein
        g.db = sqlite3.connect(DATABASE, timeout=10, check_same_thread=False)
        g.db.row_factory = sqlite3.Row  # Isse plant['name'] wala error khatam ho jayega
    return g.db

@app.teardown_appcontext
def close_db(error):
    """Request khatam hone par connection close karne ke liye"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def add_column_if_not_exists(cursor, table, column_def):
    """Database mein column add karne ka safe tarika taaki error na aaye"""
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")
    except sqlite3.OperationalError:
        pass  # Column pehle se hai, koi tension nahi

# ----------------- DATABASE INITIALIZATION -----------------

def init_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Tables Create Karein
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        name TEXT, 
        email TEXT UNIQUE, 
        password TEXT, 
        role TEXT, 
        mobile TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS suppliers(
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER, 
        name TEXT, 
        latitude REAL DEFAULT 18.5204, 
        longitude REAL DEFAULT 73.8567, 
        FOREIGN KEY(user_id) REFERENCES users(id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        name TEXT, 
        price REAL, 
        stock INTEGER, 
        image TEXT, 
        category TEXT, 
        supplier_id INTEGER)""")
    
    
    cur.execute('''CREATE TABLE IF NOT EXISTS cart 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              user_id INTEGER, 
              product_name TEXT, 
              price REAL, 
              quantity INTEGER)''')

    cur.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER, 
        user_name TEXT, 
        supplier_id INTEGER DEFAULT 0, 
        product_name TEXT, 
        price REAL, 
        quantity INTEGER, 
        total REAL, 
        status TEXT DEFAULT 'Pending', 
        payment_method TEXT, 
        location TEXT, 
        mobile TEXT, 
        payment_id TEXT, 
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")

    cur.execute("CREATE TABLE IF NOT EXISTS diseases(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, image TEXT, fertilizer_id INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS fertilizers(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, price REAL NOT NULL, stock INTEGER NOT NULL, image TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS feedbacks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product TEXT, message TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")

    # 2. Columns safely add karein (ALTER TABLE fix)
    add_column_if_not_exists(cur, "suppliers", "upi_id TEXT")
    add_column_if_not_exists(cur, "suppliers", "qr_code TEXT")
    add_column_if_not_exists(cur, "suppliers", "payment_mobile TEXT")
    add_column_if_not_exists(cur, "suppliers", "address TEXT")
    add_column_if_not_exists(cur, "orders", "payment_settled INTEGER DEFAULT 0")
    add_column_if_not_exists(cur, "orders", "admin_commission REAL DEFAULT 0")

    # 3. Default Products Insert Logic
    products_list = [
        ("Apple Plant", 120, 50, "appleplant.png", "plant", 0),
        ("Banana Plant", 80, 40, "banana.png", "plant", 0),
        ("Sunflower Seeds", 60, 100, "sunflower.png", "seed", 0),
        ("Wheat Seed", 149, 100, "wheat.png", "seed", 0)
    ]
    for p in products_list:
        cur.execute("SELECT id FROM products WHERE name=?", (p[0],))
        if not cur.fetchone():
            cur.execute("INSERT INTO products(name, price, stock, image, category, supplier_id) VALUES (?,?,?,?,?,?)", p)
    
    # 4. Old data migration (Supplier check)
    cur.execute("SELECT user_id FROM suppliers LIMIT 1")
    sup = cur.fetchone()
    if sup:
        cur.execute("UPDATE products SET supplier_id=? WHERE supplier_id=0 OR supplier_id IS NULL", (sup['user_id'],))

    conn.commit()
    conn.close()
    print("✅ Database Synchronized!")
with app.app_context():
    init_db()
    print("✅ Database initialized!")
# Root route
# 1. ROOT ROUTE (Redirects based on session)
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login_page"))  # Redirect to the GET route below
    
    role = session.get("role")
    if role == "customer":
        return redirect("/home")
    elif role == "admin":
        return redirect("/admin")
    elif role == "supplier":
        return redirect("/supplier")
    else:
        return "Access Denied", 403

@app.context_processor
def inject_translations():
    # Session se language uthayein, default 'en'
    lang = session.get('lang', 'en')
    
    # Ye check karein ki 'translations' variable load hua hai ya nahi
    try:
        current_texts = translations.get(lang, translations.get('en', {}))
    except NameError:
        current_texts = {} # Agar translations load nahi hua toh khali dict bhejien taaki crash na ho
        
    return dict(texts=current_texts)

@app.route("/login", methods=["GET"])
def login_page():
    return render_template("Sign_Up.html")

# 3. LOGIN ACTION (POST) - This processes the data
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "") 
        
        db = get_db()
        # Sirf wahi user dhoondo jiska email match kare
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

        if user:
            # Bcrypt se password verify karo
            if bcrypt.check_password_hash(user['password'], password):
                session.permanent = True
                session["user_id"] = user['id']
                session["role"] = user['role']
                session["username"] = user['name']
                
                # Role ke hisaab se sahi jagah bhejo
                if user['role'] == "admin": return redirect("/admin")
                elif user['role'] == "supplier": return redirect("/supplier")
                else: return redirect("/home")
            else:
                return "Invalid Password! ❌", 401
        else:
            return "Account not found! Please Sign Up first. ❌", 404

    return render_template("Sign_Up.html")

@app.route("/signup", methods=["POST"])
def signup():

    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    mobile = request.form.get("mobile")
    role = request.form.get("role")

    # password hash
    hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
    
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
        INSERT INTO users (name, email, password, role, mobile)
        VALUES (?, ?, ?, ?, ?)
        """, (name, email, hashed_password, role, mobile))

        conn.commit()

        return "Signup Successful"

    except sqlite3.IntegrityError:
        return "Email already exists ❌"

    finally:
        conn.close()

# Customer dashboard
@app.route("/home")
def home():
    if "user_id" not in session:
        return redirect("/login")

    if session.get("role") != "customer":
        return "Access Denied"

    lang = session.get('lang', 'en')
    texts = translations[lang]

    return render_template("Home.html", username=session.get("username"), texts=texts)


@app.route('/set_language/<lang_code>')
def set_language(lang_code):
    if lang_code in translations:
        session['lang'] = lang_code
    return redirect(request.referrer or url_for('start'))
    

# ------------------------------------- COMMON PAGES -------------------------------------------------#

@app.route("/search")
def search():
    query = request.args.get("q", "").lower()

    conn = get_db()
    cur = conn.cursor()

    # search in all categories
    cur.execute("""
        SELECT * FROM products 
        WHERE LOWER(name) LIKE ?
    """, ('%' + query + '%',))

    results = cur.fetchall()
    conn.close()

    return render_template("search_results.html", results=results, query=query)

# --------------------------------PLANTS-------------------------------------#
# --- PLANTS PAGE ROUTE ---
@app.route("/plants")
def plants_page():
    db = get_db()
    
    plants = db.execute('''
        SELECT p.*, u.name as supplier_name 
        FROM products p 
        LEFT JOIN users u ON p.supplier_id = u.id 
        WHERE p.category = 'plant'
    ''').fetchall()
    return render_template("plants.html", plants=plants)

# --- SEEDS PAGE ROUTE ---
@app.route("/seeds")
def seeds_page():
    db = get_db()
    seeds = db.execute('''
        SELECT p.*, u.name as supplier_name 
        FROM products p 
        LEFT JOIN users u ON p.supplier_id = u.id 
        WHERE p.category = 'seed'
    ''').fetchall()
    return render_template("seeds.html", seeds=seeds)
# --------------------------------FERTILIZERS -------------------------------------#
@app.route("/fertilizers")
def fertilizers_page():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM fertilizers")
    fertilizers = cur.fetchall()
    return render_template("fertilizers.html", fertilizers=fertilizers)
@app.route("/diseases")
def diseases_page():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM diseases")
    diseases = cur.fetchall()

    conn.close()

    return render_template("diseases.html", diseases=diseases)
@app.route("/fertilizer/<int:id>")
def fertilizer_by_disease(id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT f.*
        FROM diseases d
        JOIN fertilizers f ON d.fertilizer_id = f.id
        WHERE d.id=?
    """, (id,))

    fertilizer = cur.fetchone()

    conn.close()

    return render_template("fertilizer_view.html", fertilizer=fertilizer)
# --------------------------------ORDERS-------------------------------------#
@app.route("/orders")
def orders_page():
    if "user_id" not in session:
        return redirect("/login")
    user_id = session["user_id"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    orders = cur.fetchall()
    return render_template("Orderss.html", orders=orders)
@app.route("/order_history")
def order_history():
    user_id = session.get("user_id")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM orders 
        WHERE user_id=? 
        ORDER BY id DESC
    """, (user_id,))

    orders = cursor.fetchall()
    conn.close()

    return render_template("history.html", orders=orders)
@app.route("/confirm_order", methods=["POST"])
def confirm_order():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Login required"})

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data received"})

    cart = data.get("cart")
    location = data.get("location")
    user_id = session.get("user_id")
    user_name = session.get("username")
    mobile = session.get("mobile")

    db = get_db()
    try:
        for item in cart:
            # --- 🛡️ CRITICAL STEP: Product se Supplier ID nikalo ---
            # Agar product table mein supplier_id 0 hai ya null, toh default 1 (Admin) ko assign karo
            res = db.execute("SELECT supplier_id FROM products WHERE name = ?", (item["name"],)).fetchone()
            
            # Agar res milta hai aur usme id hai toh wo use karo, warna default 1
            s_id = res['supplier_id'] if (res and res['supplier_id'] != 0) else 1

            total = float(item["price"]) * int(item["quantity"])

            # --- Ab Insert karte waqt supplier_id daalo ---
            db.execute("""
                INSERT INTO orders(
                    user_id, user_name, mobile,
                    product_name, price, quantity,
                    total, location, status, supplier_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                user_id, user_name, mobile,
                item["name"], item["price"], item["quantity"],
                total, location, "Pending", s_id
            ))

            # Stock kam karo
            db.execute("UPDATE products SET stock = stock - ? WHERE name = ?", 
                       (item["quantity"], item["name"]))

        db.commit()
        return jsonify({"success": True})

    except Exception as e:
        print("❌ Order Logic Error:", e)
        return jsonify({"success": False, "message": str(e)})
# --------------------------------PAYMENTS-------------------------------------#
# Remove order
@app.route("/remove_order/<int:order_id>", methods=["POST"])
def remove_order(order_id):
    if "user_id" not in session:
        return redirect("/login")
    conn = get_db()
    cur = conn.cursor()
    # Only allow removing pending orders for this user
    cur.execute("DELETE FROM orders WHERE id=? AND user_id=? AND status='Pending'", 
                (order_id, session["user_id"]))
    conn.commit()
    return redirect("/orders")

# Buy Now (redirect to payment page)
@app.route("/buy_now/<int:order_id>", methods=["POST"])
def buy_now(order_id):
    if "user_id" not in session:
        return redirect("/login")
    conn = get_db()
    cur = conn.cursor()
    # Fetch the order details
    cur.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, session["user_id"]))
    order = cur.fetchone()
    if not order:
        return "Order not found ❌"
    # Redirect to payment page (you can use a template to confirm payment)
    return render_template("Payments.html", orders=[order])

# --------------------------------FEEDBACK -------------------------------------#
@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    # ✅ FIXED HERE
    cur.execute("SELECT DISTINCT product_name FROM orders WHERE user_id=?", (user_id,))
    products = [p[0] for p in cur.fetchall()]

    if request.method == "POST":
        product = request.form["product"]
        message = request.form["message"]

        cur.execute(
            "INSERT INTO feedbacks (user_id, product, message) VALUES (?, ?, ?)",
            (user_id, product, message)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("feedback"))

    conn.close()
    return render_template("Feedbacks.html", products=products)

# --------------------------------ADMIN/FEEDBACKS-------------------------------------#
@app.route("/admin/feedbacks")
def admin_feedbacks():
    # Check if admin is logged in
    if session.get("role") != "admin":
        return "Access Denied"

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    # Fetch all feedbacks with user name
    cur.execute("""
        SELECT feedbacks.id, users.name, feedbacks.product, feedbacks.message, feedbacks.created_at
        FROM feedbacks
        JOIN users ON feedbacks.user_id = users.id
        ORDER BY feedbacks.id DESC
    """)
    feedbacks = cur.fetchall()
    conn.close()

    return render_template("admin_feedbacks.html", feedbacks=feedbacks)


# --------------------------------ADMIN-------------------------------------#
@app.route("/admin")
def admin_dashboard():
    # 1. Session Check (Zaroori hai)
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login_page"))
        
    db = get_db()
    
    # 2. Dashboard Stats
    total_orders = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] or 0
    total_revenue = db.execute("SELECT SUM(total) FROM orders").fetchone()[0] or 0
    total_customers = db.execute("SELECT COUNT(*) FROM users WHERE role='customer'").fetchone()[0] or 0
    total_products = db.execute("SELECT COUNT(*) FROM products").fetchone()[0] or 0

    # 3. Recent Orders (Added 'mobile', 'location', and 'payment_method' for Modal)
    # Note: Hum 'user_name' direct orders table se le rahe hain ya join se, dono check karein
    raw_recent = db.execute("""
        SELECT o.*, u.name as customer_name, u.mobile, u.role
        FROM orders o
        LEFT JOIN users u ON o.user_id = u.id
        ORDER BY o.id DESC LIMIT 10
    """).fetchall()
    
    # CRITICAL FIX: Row object ko Dictionary mein badlo
    recent_orders = [dict(row) for row in raw_recent]

    # 4. Unsettled Orders
    raw_unsettled = db.execute("""
        SELECT o.id, o.product_name, o.total, COALESCE(s.name, 'Unknown') as supplier_name
        FROM orders o
        LEFT JOIN users s ON o.supplier_id = s.id
        WHERE o.status = 'Delivered' AND (o.payment_settled = 0 OR o.payment_settled IS NULL)
    """).fetchall()
    
    # CRITICAL FIX: Isse bhi Dictionary mein badlo
    unsettled_orders = [dict(row) for row in raw_unsettled]

    return render_template("admin_index.html", # <--- Iska naam sahi karein
        total_products=total_products, 
        total_orders=total_orders, 
        total_customers=total_customers, 
        total_revenue=total_revenue, 
        orders=recent_orders,
        active='dashboard')
# --- NAYA: Payment Settle karne ka Route ---
@app.route("/payment/<int:order_id>")
def payment_pageo(order_id):
    if "user_id" not in session:
        return redirect("/login")
        
    db = get_db()
    # Order ki poori detail fetch karein
    order = db.execute("""
        SELECT o.*, p.name as product_name 
        FROM orders o 
        JOIN products p ON o.product_id = p.id 
        WHERE o.id = ?
    """, (order_id,)).fetchone()

    if not order:
        return "Order Not Found", 404

    # Yahan 'order' variable ko template mein pass karna zaroori hai
    return render_template("payment.html", order=order)
# --------------------------------SUPPLIER -------------------------------------#

# ... (baaki imports aur app setup) ...
@app.route('/supplier')
def supplier_dashboard():
    if 'user_id' not in session or session.get('role') != 'supplier':
        return redirect('/login')

    supplier_id = session['user_id']
    db = get_db()

    # LEFT JOIN use karein taaki agar user details missing bhi hon toh order dikhe
    orders = db.execute("""
    SELECT 
        o.id, o.product_name, o.quantity, o.total, o.status, o.location,
        o.payment_method, o.payment_settled,
        u.name AS user_name, u.mobile AS user_mobile
    FROM orders o
    LEFT JOIN users u ON o.user_id = u.id 
    WHERE o.supplier_id = ?
    ORDER BY o.id DESC
""", (supplier_id,)).fetchall()
    return render_template('supplier.html', orders=orders)

@app.route('/contact')
def contact_view(): # Naam badal diya taaki conflict na ho
    # Google Maps ka correct embed URL (No errors)
    map_url = "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3781.332306353982!2d73.7661595751936!3d18.60411888251214!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x3bc2b97950949d97%3A0x600f7e6f8094d214!2sPimpri-Chinchwad%2C%20Maharashtra!5e0!3m2!1sen!2sin!4v1711912345678!5m2!1sen!2sin"
    return render_template('contact.html', map_url=map_url)
@app.route("/supplier_action/<int:order_id>", methods=["POST"])
def supplier_action(order_id):
    if "user_id" not in session or session.get("role") != "supplier":
        return redirect("/login")

    action = request.form.get("action")
    db = get_db()
    
    # 1. Jab supplier order accept karega
    if action == "accept":
        new_status = "Accepted"
        
    # 2. Jab supplier nursery se niklega (Out for Delivery)
    elif action == "out_for_delivery":
        new_status = "On the Way"
        
    # 3. Jab supplier customer ke ghar deliver kar dega
    elif action == "deliver":
        new_status = "Delivered"
        
    # 4. Agar reject karna ho
    elif action == "reject":
        new_status = "Rejected"
    else:
        return redirect("/supplier")

    # Database mein status update kar do
    db.execute("UPDATE orders SET status=? WHERE id=?", (new_status, order_id))
    db.commit()
    
    print(f"DEBUG: Order {order_id} status updated to {new_status}")
    return redirect("/supplier")
@app.route("/supplier/add_product_page")
def add_product_page():
    if "user_id" not in session or session.get("role") != "supplier":
        return redirect("/login")
    return render_template("add_product.html")

# 2. Data Save Karne Ke Liye (POST)
@app.route("/supplier/add_product", methods=["POST"])
def supplier_add_product():
    if "user_id" not in session:
        return redirect("/login")

    name = request.form.get("name")
    price = request.form.get("price")
    stock = request.form.get("stock")
    category = request.form.get("category")
    
    # Image Handling
    image = request.files.get("image")
    image_name = "default_plant.png"
    if image:
        image_name = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_name))

    db = get_db()
    db.execute("""
        INSERT INTO products (name, price, stock, image, category, supplier_id) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, price, stock, image_name, category, session['user_id']))
    db.commit()
    
    return redirect("/supplier") # Wapas dashboard par bhej dega
# --------------------------------ASSIGN_SUPPLIER -------------------------------------#
@app.route("/update_order/<int:id>/<status>")
def update_order(id, status):
    db = get_db()
    db.execute("UPDATE orders SET status=? WHERE id=?", (status, id))
    db.commit()
    return redirect("/supplier")


# --------------------------------UPDATE_STATUS -------------------------------------#

@app.route("/update_status/<int:order_id>", methods=["POST"])
def update_status(order_id):
    if session.get("role") != "admin":
        return "Access Denied"

    status = request.form["status"]

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit()
    conn.close()

    return redirect("/admin/orders")
# --------------------------------ADMIN CREATE(RUN ONCE)------------------------------#
@app.route("/create_admin")
def create_admin_route(): # Naam change kiya taki function conflict na ho
    db = get_db()
    # Password ko dhyan se hash karein
    hashed_pw = bcrypt.generate_password_hash("admin123").decode("utf-8")
    
    try:
        db.execute(
            "INSERT INTO users (name, email, password, role, mobile) VALUES (?, ?, ?, ?, ?)",
            ("Admin User", "admin@gmail.com", hashed_pw, "admin", "9999999999")
        )
        db.commit()
        return "✅ Admin Account Created! Email: admin@gmail.com, Pass: admin123"
    except Exception as e:
        return f"❌ Error: {str(e)} (Shayad admin pehle se exist karta hai)"
# --------------------------------SUPPLIER-------------------------------------#
@app.route("/create_supplier")
def create_supplier():
    db = get_db()
    cur = db.cursor()

    password = bcrypt.generate_password_hash("supplier123").decode("utf-8")

    try:
        cur.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            ("Supplier", "supplier@gmail.com", password, "supplier")
        )
        db.commit()
    except:
        pass

    db.close()
    return "Supplier Created"

# --------------------------------LOGOUT-------------------------------------#
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
# --------------------------------VERIFY_ORDER--------------------------------#
@app.route("/verify_order/<mobile>")
def verify_order(mobile):
    message = "Your order is confirmed ✅ Thank you for shopping with us!"
    
    encoded_message = quote(message)
    whatsapp_url = f"https://wa.me/91{mobile}?text={encoded_message}"
    
    return redirect(whatsapp_url)
 
from urllib.parse import quote
# --------------------------------VERIFACATOIN MASSAGE-----------------------# 

@app.route("/admin/orders")
def admin_orders():

    if "user_id" not in session or session.get("role") != "admin":
        return redirect("/")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM orders ORDER BY id DESC")
    orders = cur.fetchall()

    conn.close()

    return render_template("admin_orders.html", orders=orders)

# Add Product
@app.route("/admin/add_product", methods=["GET", "POST"])
def admin_add_product():
    # SECURITY: Check karein ki user Admin hai ya nahi
    if "user_id" not in session or session.get("role") != "admin":
        flash("Unauthorized access! Please login as admin.", "danger")
        return redirect(url_for("login_page"))

    if request.method == "POST":
        # Form se data nikalna
        name = request.form.get("name")
        price = request.form.get("price")
        stock = request.form.get("stock")
        category = request.form.get("category")
        
        # Image handle karna
        file = request.files.get('image')
        filename = ""

        if file and file.filename != '':
            # Secure filename taaki koi galat file upload na kare
            filename = secure_filename(file.filename)
            
            # Folder check karein (agar nahi hai toh bana dega)
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            filename = "default_plant.png" # Agar image na ho toh backup

        # Database mein save karna
        try:
            db = get_db()
            db.execute("""
                INSERT INTO products (name, price, stock, image, category, supplier_id) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, price, stock, filename, category.lower(), session['user_id']))
            db.commit()
            
            flash("Product Added Successfully! ✅", "success")
            return redirect("/admin/products") # Manage products page par bhejo
            
        except Exception as e:
            print(f"Error adding product: {e}")
            flash("Database Error! ❌", "danger")
            return redirect(url_for("admin_add_product"))

    # GET request: Sirf form dikhao
    return render_template("admin_add_product.html", active='add_product')
@app.route("/admin/products")
def manage_products():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    conn.close()

    return render_template("admin_products.html", products=products)

# Customers
@app.route("/admin/customers")
def admin_customers():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, mobile FROM users WHERE role='customer'")
    customers = cur.fetchall()
    conn.close()

    return render_template("admin_customers.html", customers=customers)
# Reports
@app.route("/admin/reports")
def admin_reports():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("SELECT SUM(total_price) FROM orders")
    result = cur.fetchone()[0]

    revenue = result if result else 0

    conn.close()

    return render_template("admin_reports.html", revenue=revenue)
@app.route("/success")
def success():
    return "Payment Successful!"

from flask import request, session

@app.route("/update_location", methods=["POST"])
def update_location():
    data = request.get_json()
    lat = data['lat']
    lng = data['lng']

    supplier_id = session.get("supplier_id")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE suppliers 
        SET latitude=?, longitude=? 
        WHERE id=?
    """, (lat, lng, supplier_id))

    conn.commit()
    conn.close()

    return "OK"

# --- YE AKELA FUNCTION RAKHEIN, BAAKI DO DELETE KAR DEIN ---
from flask import jsonify # Sabse upar check karein ye import hai ya nahi


@app.route("/admin/approve_order/<int:order_id>")
def approve_order(order_id):
    # Security: Sirf admin hi approve kar sake
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    # 1. Status ko 'Confirmed' karein 
    # 2. payment_settled ko 1 (True) karein
    db.execute("""
        UPDATE orders 
        SET status='Confirmed', payment_settled=1 
        WHERE id=?
    """, (order_id,))
    
    db.commit()
    flash("Order verified and confirmed successfully!", "success")
    return redirect(url_for('admin_orders')) # Apne orders route ka naam yahan likhein
# --- PAYMENT PAGE ROUTE ---
# -------------------------------- FINAL PAYMENT LOGIC -------------------------------- #
@app.route("/payments")
def payments():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    db = get_db()
    
    # Admin ka mobile number
    admin_data = db.execute("SELECT mobile FROM users WHERE role='admin' LIMIT 1").fetchone()
    admin_mobile = admin_data['mobile'] if admin_data else "9999999999"

    # Pending aur History orders fetch karna
    pending_orders = db.execute("SELECT * FROM orders WHERE user_id=? AND status='Pending'", (user_id,)).fetchall()
    history_orders = db.execute("SELECT * FROM orders WHERE user_id=? AND status != 'Pending' ORDER BY id DESC", (user_id,)).fetchall()

    # Total calculate karna
    total = round(float(item["price"]) * int(item["quantity"]), 2)
    # FIX: variable ka naam 'total_amt' rakhein jo HTML mein use hua hai
    return render_template("Payments.html", 
                       orders=pending_orders, 
                       history=history_orders, 
                       total_amt=total,
                       admin_mobile=admin_mobile,
                       upi_id="yourname@upi")
@app.route("/place_order", methods=["POST"])
def place_order_action():
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "Session expired! Please login again."}), 401

    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No data received!"}), 400

    method = data.get("method")
    utr = data.get("utr")
    user_id = session["user_id"]
    user_name = session.get("username")
    
    db = get_db()
    
    try:
        # 1. Cart se items uthao
        cart_items = db.execute("SELECT * FROM cart WHERE user_id = ?", (user_id,)).fetchall()
        
        if not cart_items:
            return jsonify({"status": "error", "message": "Cart is empty!"}), 400

        for item in cart_items:
            # Status logic (UPI ke liye alag, COD ke liye alag)
            status = "Pending Approval" if method == "UPI" else "Pending"
            
            # 2. Product table se supplier_id nikalna (Taki supplier ko uska order dikhe)
            prod = db.execute("SELECT supplier_id FROM products WHERE name=?", (item['product_name'],)).fetchone()
            
            # Agar product ka koi supplier nahi hai, toh Admin (ID: 1) ko assign kar do
            s_id = prod['supplier_id'] if (prod and prod['supplier_id']) else 1

            # 3. Total Price Calculation (Float/Int conversion zaroori hai)
            item_price = float(item['price'])
            item_qty = int(item['quantity'])
            total_amt = round(item_price * item_qty, 2)

            # 4. Order Table mein Insert karein
            db.execute("""
                INSERT INTO orders (
                    user_id, user_name, product_name, price, quantity, total, 
                    status, payment_method, payment_id, supplier_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, user_name, item['product_name'], item_price, item_qty, 
                total_amt, status, method, utr, s_id
            ))

        # 5. Order ke baad cart khali karein
        db.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        db.commit()
        
        return jsonify({"status": "success", "message": "Order placed successfully! ✅"})

    except Exception as e:
        db.rollback() # Error aane par changes cancel karein
        print(f"❌ Order Error: {e}")
        return jsonify({"status": "error", "message": "Something went wrong while placing order."}), 500
@app.route('/get_supplier_location/<int:order_id>')
def get_supplier_location(order_id):
    # Maan lijiye aapka database order status check karta hai
    # Yahan hum example coordinates de rahe hain (e.g., Pune/Mumbai area)
    location_data = {
        "lat": 18.5204, 
        "lng": 73.8567,
        "status": "On the Way"
    }
    return jsonify(location_data)
@app.route('/payment_history')
def payment_history():
    # Database se payments fetch karein (example query)
    # payments = db.execute("SELECT * FROM payments WHERE customer_id = ?", (user_id,))
    
    # Example data: Supplier ki location manually ya DB se aayegi
    # Google Maps Embed URL format: googleusercontent.com/maps.google.com/0`—suggests2
    supplier_location = "Mumbai+Nursery+Market" 
    map_url = f"googleusercontent.com/maps.google.com/0`—suggests3"

    return render_template('payment_history.html', map_url=map_url)
@app.route("/update_supplier_location", methods=["POST"])
def update_supplier_location():
    # Supplier ki ID session se uthao
    supplier_id = session.get("supplier_id") 
    if not supplier_id:
        return {"status": "error", "message": "Not logged in as supplier"}, 401

    data = request.get_json()
    lat = data.get('latitude')
    lng = data.get('longitude')

    try:
        db = get_db()
        # Supplier ki table mein latitude aur longitude update karo
        db.execute("""
            UPDATE suppliers 
            SET latitude = ?, longitude = ? 
            WHERE id = ?
        """, (lat, lng, supplier_id))
        db.commit()
        return {"status": "success"}, 200
    except Exception as e:
        print(f"Location Update Error: {e}")
        return {"status": "error"}, 500
    
import os
from werkzeug.utils import secure_filename

# Static folder ke andar images folder hona chahiye
UPLOAD_FOLDER = 'static/images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
@app.route("/fix_db")
def fix_db():
    db = get_db()
    # Maan lo aapki Supplier ki User ID '2' hai (Check in Users table)
    # Ye query saare 0 wale orders ko ID 2 wale supplier ko assign kar degi
    db.execute("UPDATE orders SET supplier_id = 2 WHERE supplier_id = 0 OR supplier_id IS NULL")
    db.commit()
    return "✅ Database Fix Ho Gaya! Ab Supplier Dashboard check karein."

@app.route('/admin/delete_product/<int:id>', methods=['POST'])
def delete_product(id):
    db = get_db()
    db.execute("DELETE FROM products WHERE id = ?", (id,))
    db.commit()
    return redirect(url_for('manage_products'))

@app.route("/supplier/profile", methods=["GET", "POST"])
def supplier_profile():
    if session.get("role") != "supplier":
        return redirect("/login")

    db = get_db()

    if request.method == "POST":
        upi = request.form.get("upi_id")
        mobile = request.form.get("payment_mobile")
        address = request.form.get("address")

        qr = request.files.get("qr")
        qr_name = ""

        if qr:
            qr_name = secure_filename(qr.filename)
            qr.save(os.path.join(app.config['UPLOAD_FOLDER'], qr_name))

        db.execute("""
            UPDATE suppliers 
            SET upi_id=?, payment_mobile=?, address=?, qr_code=?
            WHERE user_id=?
        """, (upi, mobile, address, qr_name, session["user_id"]))

        db.commit()
        return "Profile Saved"

    return render_template("supplier_profile.html")
if __name__ == "__main__":
    init_db() 
    # Render ke liye port environment variable se lena behtar hai
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)