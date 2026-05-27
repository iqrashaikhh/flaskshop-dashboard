from flask import Flask, render_template, request, redirect, session, flash,url_for
from flask_mysqldb import MySQL
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.secret_key = "secretkey"

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'flask_auth'

mysql = MySQL(app)


oauth = OAuth(app)

google = oauth.register(
    name='google',
    client_id='YOUR_CLIENT_ID',
    client_secret='YOUR_CLIENT_SECRET',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("login.html")


# ---------------- REGISTER PAGE ----------------

@app.route("/register")
def register_page():
    return render_template("register.html")

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route('/google-callback')
def google_callback():
    token = google.authorize_access_token()

    user_info = google.get(
        'https://www.googleapis.com/oauth2/v1/userinfo'
    ).json()

    name = user_info['name']
    email = user_info['email']

    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cur.fetchone()

    if not user:
        cur.execute(
            "INSERT INTO users(name,email,password) VALUES(%s,%s,%s)",
            (name, email, "google_auth")
        )
        mysql.connection.commit()

        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

    cur.close()

    session["user"] = user[1]
    session["user_id"] = user[0]

    flash("Logged in with Google", "success")

    return redirect("/dashboard")
# ---------------- REGISTER USER ----------------

@app.route("/register", methods=["POST"])
def register():

    name = request.form["name"]
    email = request.form["email"]
    password = request.form["password"]

    cur = mysql.connection.cursor()

    cur.execute(
        "INSERT INTO users(name,email,password) VALUES(%s,%s,%s)",
        (name, email, password)
    )

    mysql.connection.commit()
    cur.close()

    flash("Registration Successful!", "success")

    return redirect("/")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["POST"])
def login():

    email = request.form["email"]
    password = request.form["password"]

    cur = mysql.connection.cursor()

    cur.execute(
        "SELECT * FROM users WHERE email=%s AND password=%s",
        (email, password)
    )

    user = cur.fetchone()
    cur.close()

    if user:
        session["user"] = user[1]
        session["user_id"] = user[0]

        flash("Login Successful", "success")

        return redirect("/dashboard")

    flash("Invalid Email or Password", "danger")

    return redirect("/")


@app.route('/api/cart-count')
def cart_count():

    if "user_id" not in session:
        return {"count": 0, "total": 0}

    user_id = session["user_id"]
    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT products.price, cart.quantity
    FROM cart
    JOIN products ON cart.product_id = products.id
    WHERE cart.user_id = %s
    """, (user_id,))

    items = cur.fetchall()
    cur.close()

    total = sum(item[0] * item[1] for item in items)
    count = sum(item[1] for item in items)

    return {
        "count": count,
        "total": total
    }  



@app.route('/api/products-count')
def products_count():

    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) FROM products")
    count = cur.fetchone()[0]

    cur.close()

    return {"count": count}




# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    if "user" in session:
        return render_template("dashboard.html", name=session["user"])

    return redirect("/")


# ---------------- PRODUCTS ----------------

@app.route("/products")
def products():

    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM products")

    products = cur.fetchall()

    cur.close()

    return render_template("products.html", products=products)


# ---------------- ADD TO CART ----------------
@app.route("/add-to-cart/<int:id>")
def add_to_cart(id):

    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]
    cur = mysql.connection.cursor()

    # Check if already in cart
    cur.execute(
        "SELECT * FROM cart WHERE user_id=%s AND product_id=%s",
        (user_id, id)
    )
    existing = cur.fetchone()

    if existing:
        cur.execute(
            "UPDATE cart SET quantity = quantity + 1 WHERE user_id=%s AND product_id=%s",
            (user_id, id)
        )
    else:
        cur.execute(
            "INSERT INTO cart(user_id, product_id, quantity) VALUES(%s,%s,1)",
            (user_id, id)
        )

    mysql.connection.commit()
    cur.close()

    return redirect("/cart")


@app.route('/increment/<int:id>')
def increment(id):

    user_id = session["user_id"]
    cur = mysql.connection.cursor()

    cur.execute("""
    UPDATE cart 
    SET quantity = quantity + 1 
    WHERE user_id=%s AND product_id=%s
    """, (user_id, id))

    mysql.connection.commit()
    cur.close()

    return redirect('/cart')



@app.route('/decrement/<int:id>')
def decrement(id):

    user_id = session["user_id"]
    cur = mysql.connection.cursor()

    # decrease but not below 1
    cur.execute("""
    UPDATE cart 
    SET quantity = quantity - 1 
    WHERE user_id=%s AND product_id=%s AND quantity > 1
    """, (user_id, id))

    mysql.connection.commit()
    cur.close()

    return redirect('/cart')



@app.route('/remove/<int:id>')
def remove(id):

    user_id = session["user_id"]
    cur = mysql.connection.cursor()

    cur.execute("""
    DELETE FROM cart 
    WHERE user_id=%s AND product_id=%s
    """, (user_id, id))

    mysql.connection.commit()
    cur.close()

    return redirect('/cart')

# ---------------- CART PAGE ----------------

@app.route("/cart")
def cart():

    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
    SELECT products.id, products.name, products.price, cart.quantity, products.image
    FROM cart
    JOIN products ON cart.product_id = products.id
    WHERE cart.user_id = %s
    """, (user_id,))

    items = cur.fetchall()
    cur.close()

    return render_template("cart.html", items=items)

# ---------------- PROFILE ----------------

@app.route("/profile")
def profile():

    if "user_id" not in session:
        return redirect("/")

    cur = mysql.connection.cursor()

    cur.execute(
        "SELECT name,email FROM users WHERE id=%s",
        (session["user_id"],)
    )

    user = cur.fetchone()

    cur.close()

    return render_template("profile.html", user=user)


# ---------------- ADMIN DASHBOARD ----------------

@app.route("/admin")
def admin():

    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM products")

    products = cur.fetchall()

    cur.close()

    return render_template("admin_dashboard.html", products=products)



@app.route('/edit-product/<int:id>')
def edit_product(id):

    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM products WHERE id=%s", (id,))
    product = cur.fetchone()

    cur.close()

    return render_template("edit_product.html", product=product)



@app.route('/update-product/<int:id>', methods=["POST"])
def update_product(id):

    name = request.form["name"]
    price = request.form["price"]
    image = request.form["image"]
    description = request.form["description"]

    cur = mysql.connection.cursor()

    cur.execute("""
        UPDATE products 
        SET name=%s, price=%s, image=%s, description=%s 
        WHERE id=%s
    """, (name, price, image, description, id))

    mysql.connection.commit()
    cur.close()

    flash("Product Updated Successfully", "success")

    return redirect('/admin')


@app.route('/delete-product/<int:id>')
def delete_product(id):

    cur = mysql.connection.cursor()

    cur.execute("DELETE FROM products WHERE id=%s", (id,))
    mysql.connection.commit()

    cur.close()

    flash("Product Deleted Successfully", "danger")

    return redirect('/admin')


    


# ---------------- ADD PRODUCT ----------------

@app.route("/add-product", methods=["POST"])
def add_product():

    name = request.form["name"]
    price = request.form["price"]
    image = request.form["image"]
    description = request.form.get("description")  # safe

    cur = mysql.connection.cursor()

    cur.execute(
        "INSERT INTO products(name,price,image,description) VALUES(%s,%s,%s,%s)",
        (name, price, image, description)
    )

    mysql.connection.commit()
    cur.close()

    return redirect("/admin")


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    flash("Logged Out Successfully", "info")

    return redirect("/")


# ---------------- RUN SERVER ----------------

if __name__ == "__main__":
    app.run(debug=True , port=5001)