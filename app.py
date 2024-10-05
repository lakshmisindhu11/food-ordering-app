from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
import random
import math
from fpdf import FPDF
import os
from bson import ObjectId
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import datetime
from bson.json_util import dumps


app = Flask(__name__, static_folder='static')
app.secret_key = 'your_secret_key'

MONGO_URI = "mongodb+srv://nithin:nithin@cluster0.ohw9t2m.mongodb.net/Foodie?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)

db = client.get_database('Foodie')
user_collection = db.users
menu_collection = db.menu
feedback_collection=db.feedback

# Configure the upload folder
app.config["UPLOAD_FOLDER"] = "static/profile_photos/"
if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])
    
@app.route('/menu')
def show_menu():
    menu_data = list(menu_collection.find({}))
    return render_template("Menu.html", menu=menu_data)

@app.route('/home')
def home():
    if 'email' in session:
        user = user_collection.find_one({"email": session['email']})
        return render_template("Home.html", user=user)
    return redirect(url_for('login'))

@app.route('/reservation')
def reservation():
    return render_template("Reservation.html")

@app.route('/confirm_reser', methods=["POST"])
def confirm_reser():
    if request.method == "POST":
        people = request.form.get("people")
        date = request.form.get("date")
        time = request.form.get("time")

        email = session.get("email")
        if email:
            user = user_collection.find_one({"email": email})
            if user:
                # Ensure reservation field is an array
                if not isinstance(user.get('reservation'), list):
                    user_collection.update_one(
                        {"email": email},
                        {"$set": {"reservation": []}}
                    )
                
                user_collection.update_one(
                    {"email": email},
                    {"$push": {"reservation": {"date": date, "time": time, "No of people": people}}}
                )
                return jsonify(success=True, message="Reservation Successful")
            else:
                return jsonify(success=False, message="User not found"), 404
        else:
            return jsonify(success=False, message="User not logged in"), 401

    return jsonify(success=False, message="Invalid request method"), 405

@app.route('/')
def login():
    return render_template("Login.html")

@app.route('/address', methods=['POST'])
def address():
    if request.method == "POST":
        address = request.form.get('address')
        dno = request.form.get('dno')
        landmark = request.form.get('landmark')
        email = session.get("email")

        if email:
            user_collection.update_one(
                {"email": email},
                {"$set": {"address": {"address": address, "dno": dno, "landmark": landmark}}}
            )

            # Step 2: Append the new address to the global_address array
            user_collection.update_one(
                {"email": email},
                {"$push": {"global_address": {"address": address, "dno": dno, "landmark": landmark}}}
            )

            return redirect(url_for('cart'))
        else:
            return render_template('cart.html')

    return render_template('cart.html')

@app.route('/addresses', methods=['GET'])
def addresses():
    addresses = get_addresses()
    return jsonify(addresses)

@app.route('/login_validate', methods=['POST'])
def login_validate():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        if email=='admin@admin' and password=='admin':
            return render_template('admin_login.html')
        user = user_collection.find_one({"email": email, "password": password})
        if user:
            session['email'] = email
            cart = user.get("cart", [])
            session['cart'] = cart
            return redirect(url_for('home'))
    
    return render_template('Login.html')

@app.route('/signup')
def signup():
    return render_template("SignUp.html")

@app.route('/signup_validate', methods=['POST'])
def signup_validate():
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('cpass')

        if password != confirm_password:
            return "Passwords do not match", 400

        existing_user = user_collection.find_one({"email": email})

        if existing_user:
            return "User already exists", 400

        new_user = {
            "name": name,
            "username": username,
            "email": email,
            "password": password,
            "cart": [],
            "cart_items": [],
            "global_address":[],
            "reservation":[],
            "rating":0,
            "message":"",
            "profile_photo": "default-profile.png"
        }

        user_collection.insert_one(new_user)
        return redirect(url_for('login'))

    return render_template("SignUp.html")

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    item = request.json
    email = session.get('email')
    if not email:
        return jsonify(success=False, message="User not logged in"), 401

    user = user_collection.find_one({"email": email})
    if user:
        cart = user.get("cart", [])
        # Check if the item is already in the cart and update the quantity if necessary
        item_found = False
        for cart_item in cart:
            if cart_item['name'] == item['name']:
                cart_item['quantity'] += 1
                item_found = True
                break
        if not item_found:
            cart.append(item)
        user_collection.update_one(
            {"email": email},
            {"$set": {"cart": cart}}
        )
        session['cart'] = cart
        return jsonify(success=True)
    else:
        return jsonify(success=False, message="User not found"), 404

@app.route('/clear_cart', methods=['POST'])
def clear_cart():
    email = session.get('email')
    if not email:
        return jsonify(success=False, message="User not logged in"), 401

    user_collection.update_one(
        {"email": email},
        {"$set": {"cart": []}}
    )
    session['cart'] = []
    return jsonify(success=True)

@app.route('/remove_cart', methods=['POST'])
def remove_cart_item():
    if 'email' not in session:
        return jsonify(success=False, message='User not logged in')

    data = request.json
    item_name = data.get('name')

    if not item_name:
        return jsonify(success=False, message='Item name is missing')

    email = session['email']

    # Attempt to remove the item from the user's cart using their email
    result = db.users.update_one(
        {'email': email},
        {'$pull': {'cart': {'name': item_name}}}
    )

    if result.modified_count > 0:
        return jsonify(success=True)
    else:
        return jsonify(success=False, message='Failed to remove item')


@app.route('/cart')
def cart():
    email = session.get('email')
    if email:
        user = user_collection.find_one({"email": email})
        if user:
            cart = user.get("cart", [])
            global_address = user.get("global_address", [])
            return render_template("cart.html", cart=cart, global_address=global_address)
    
    return redirect(url_for('login'))

@app.route('/save_address', methods=['POST'])
def save_address():
    address = request.json
    email = session.get('email')
    if email:
        user_collection.update_one(
            {"email": email},
            {"$set": {"address": address}}
        )
        return jsonify(success=True)
    return jsonify(success=False, message="User not logged in"), 401

@app.route('/process_payment', methods=['POST'])
def process_payment():
    email = session.get('email')
    data = request.json
    payment_method = data.get('payment')
    if email:
        user = user_collection.find_one({"email": email})
        if user:
            local_cart = user.get('cart', [])
            local_address = user.get('address', {})
            global_cart = user.get("cart_items", [])
            now = datetime.datetime.now()

            # Calculate total price
            total_price = sum(int(item.get('price', 0)) * int(item.get('quantity', 1)) for item in local_cart)

            if local_cart:
                global_cart.append({
                    "items": local_cart,
                    "address": local_address,
                    "payment_type": payment_method,
                    "Time and Date": now.strftime("%d-%m-%y, %H:%M:%S"),
                    "total_price": total_price
                })

                # Update the user's global cart and clear the local cart
                user_collection.update_one(
                    {"email": email},
                    {"$set": {"cart_items": global_cart, "cart": []}}
                )
                session['cart'] = []

                # Send the cart items via email
                sendmsg(email, local_cart, total_price)

                return jsonify(success=True, message="Cart updated and email sent successfully", total_price=total_price)
            else:
                return jsonify(success=False, message="Cart is empty"), 400
        else:
            return jsonify(success=False, message="User not found"), 404
    else:
        return jsonify(success=False, message="User not logged in"), 401


@app.route('/logout')
def logout():
    session.pop('email', None)
    session.pop('cart', None)
    return redirect(url_for('login'))

@app.route('/fetch_cart')
def fetch_cart():
    email = session.get('email')
    if not email:
        return jsonify(success=False, message="User not logged in"), 401

    user = user_collection.find_one({"email": email})
    if user:
        cart = user.get("cart", [])
        return jsonify(success=True, cart=cart)
    else:
        return jsonify(success=False, message="User not found"), 404


@app.route('/fetch_addresses')
def fetch_addresses():
    email = session.get('email')
    if email:
        user = user_collection.find_one({"email": email})
        if user:
            addresses = user.get("global_address", [])
            return jsonify(success=True, addresses=addresses)
    
    return jsonify(success=False, message="User not logged in"), 401


# Admin Section

ADMIN_EMAIL = 'admin@12'
ADMIN_PASSWORD = 'admin'


@app.route('/admin_login_validate', methods=['POST'])
def admin_login_validate():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session['admin'] = email
            return render_template('Admin.html')
    
    return redirect(url_for('admin'))

@app.route('/admin')
def admin():
    if 'admin' in session:
        return render_template("Admin.html")
    return redirect(url_for('admin_login_validate'))

@app.route('/add_menu_item', methods=['POST'])
def add_menu_item():
    category = request.form.get('category')
    name = request.form.get('name')
    price = request.form.get('price')
    description = request.form.get('description')
    image = request.files['image']

    filename = None
    if image:
        filename = secure_filename(image.filename)
        image.save(os.path.join('static', filename))

    new_item = {
        "category": category,
        "name": name,
        "price": price,
        "description": description,
        "image": filename
    }

    menu_collection.insert_one(new_item)

    return redirect(url_for('show_menu'))

@app.route('/delete_item')
def delete_item():
    return render_template('delete_menu.html')

@app.route('/delete_menu_item', methods=['POST'])
def delete_menu_item():
    name = request.json.get('name')
    
    if not name:
        return jsonify(success=False, message="Item name is required"), 400

    result = menu_collection.delete_one({"name": name})
    
    if result.deleted_count > 0:
        return jsonify(success=True, message="Item deleted successfully")
    else:
        return jsonify(success=False, message="Item not found"), 404

@app.route('/users')
def users():
    users_data = list(user_collection.find({}))
    return render_template('users.html', users=users_data)

@app.route('/user/<email>')
def user_details(email):
    user = user_collection.find_one({"email": email})
    if user:
        cart_items = user.get('cart_items', [])
        cart_groups = []
        for cart in cart_items:
            items = cart.get('items', [])
            total_price = sum(int(item['price']) * int(item['quantity']) for item in items)
            cart_groups.append({
                'items': items,
                'total_price': total_price,
                'time_and_date': cart.get('Time and Date'),
                'payment_method': cart.get('payment_type')
            })
        return render_template('user_details.html', user=user, cart_groups=cart_groups)
    else:
        return "User not found", 404



@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'email' in session:
        email = session['email']
        user = user_collection.find_one({"email": email})

        if user:
            profile_photo = request.files.get('profile_photo')
            if profile_photo:
                filename = secure_filename(profile_photo.filename)
                profile_photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                user_collection.update_one({"email": email}, {"$set": {"profile_photo": filename}})

                return jsonify(status='success', photo_url=url_for('static', filename='profile_photos/' + filename))
            else:
                return jsonify(status='error', message='No file uploaded')
        else:
            return jsonify(status='error', message='User not found')

    return jsonify(status='error', message='User not logged in')

@app.route('/GlobalCart')
def GlobalCart():
    return render_template('order_list.html')


@app.route('/fetch_Global_Cart')
def fetch_Global_Cart():
    email = session.get('email')
    if email:
        user = user_collection.find_one({"email": email})
        if user:
            gcart = user.get("cart_items", [])
            return jsonify(success=True, cart=gcart)
    
    return jsonify(success=False, message="User not logged in"), 401


# orders
def convert_objectid(o):
    if isinstance(o, ObjectId):
        return str(o)
    if isinstance(o, dict):
        return {k: convert_objectid(v) for k, v in o.items()}
    if isinstance(o, list):
        return [convert_objectid(x) for x in o]
    return o

@app.route('/past_orders')
def past_orders():
    email = session.get('email')
    user = user_collection.find_one({"email": email})

    if not user:
        return render_template('error.html', message='User not found')

    past_orders = user.get('cart_items', [])
    past_orders = convert_objectid(past_orders)

    # Add address to each order
    for order in past_orders:
        order_address = order.get('address') or user.get('address')
        order['address'] = order_address if order_address else {'dno': 'N/A', 'landmark': 'N/A', 'address': 'N/A'}
        
        if order['items']:
            order['image'] = order['items'][0]['image']
        else:
            order['image'] = 'default-image.png'  # Fallback image

    return render_template('past_orders.html', past_orders=past_orders, user=user)


@app.route('/reorder', methods=['POST'])
def reorder():
    email =session.get('email')
    user=user_collection.find_one({'email':email})
    if not email:
        return redirect(url_for('past_orders'))

    # Assuming you have a function to get orders by user email
    orders = list(user.get('cart_items', []))
    print(orders)
    if not orders:
        return redirect(url_for('past_orders'))

    last_order = orders[-1]  # Assuming the last order is to be reordered

    # Initialize or update the cart in the session
    local_cart = session.get('cart', [])

    # Add items to the cart
    for item in last_order['items']:
        # Check if item is already in the cart
        for cart_item in local_cart:
            if cart_item['name'] == item['name']:
                cart_item['quantity'] += item['quantity']
                break
        else:
            local_cart.append(item)

    session['cart'] = local_cart

    return redirect(url_for('cart'))

# @app.route('/cart')
# def cart():
#     if 'email' not in session:
#         return redirect(url_for('login'))

#     user = user_collection.find_one({'email': session['email']})
#     if user:
#         cart_items = user.get('cart', [])
#         return render_template('cart.html', cart_items=cart_items)
#     return redirect(url_for('login'))


import smtplib
import random
import math
from fpdf import FPDF
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

def sendmsg(recipient_email, cart_items,total_price):    
    # Generate OTP
   
    # Generate the PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    
    
    pdf.cell(200, 10, txt="Your cart items:", ln=True, align='L')
    for item in cart_items:
        pdf.cell(200, 10, txt=f"{item['name']} - {item['quantity']} x {item['price']}", ln=True, align='L')
        
    pdf.cell(200, 10, txt=f"Total Price: {total_price}", ln=True, align='L')
    # Save the PDF
    pdf_filename = "invoice.pdf"
    pdf.output(pdf_filename)
    
    # Create the email
    msg = MIMEMultipart()
    msg['From'] = "bezzavarapupaulbabu@gmail.com"
    msg['To'] = recipient_email
    msg['Subject'] = "Your Invoice and OTP"
    
   
    
    # Attach the PDF
    attachment = open(pdf_filename, "rb")
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(attachment.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f"attachment; filename={pdf_filename}")
    msg.attach(part)
    attachment.close()
    
    # Send the email
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login("bezzavarapupaulbabu@gmail.com","ftprgfaqioymlapq")
    text = msg.as_string()
    server.sendmail("bezzavarapupaulbabu@gmail.com", recipient_email, text)
    server.quit()
    
    # Clean up the PDF file
    os.remove(pdf_filename)


@app.route('/update_cart_quantity', methods=['POST'])
def update_cart_quantity():
    data = request.json
    name = data.get('name')
    quantity = data.get('quantity')
    email = session.get('email')
    
    if not email:
        return jsonify({'success': False, 'message': 'User not logged in'}), 401
    
    user = user_collection.find_one({"email": email})
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    local_cart = user.get('cart', [])
    if not local_cart:
        return jsonify({'success': False, 'message': 'Cart is empty'}), 400
    
    for item in local_cart:
        if item['name'] == name:
            item['quantity'] = quantity
    
    try:
        user_collection.update_one(
            {"email": email},
            {"$set": {"cart": local_cart}}
        )
        total_price = calculate_total_price()
        return jsonify({'success': True, 'total_price': total_price})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

def calculate_total_price():
    email = session.get('email')
    user = user_collection.find_one({"email": email})
    if not user:
        return 0
    local_cart = user.get('cart', [])
    total_price = sum(int(item.get('price', 0)) * int(item.get('quantity', 1)) for item in local_cart)
    return total_price


@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    try:
        data = request.json
        required_fields = ['rating', 'message']
        if any(field not in data for field in required_fields):
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        # Check if email is in the session
        email = session.get('email')
        if not email:
            return jsonify({"status": "error", "message": "User not logged in"}), 403

        # Fetch user's name from the users collection
        user = user_collection.find_one({"email": email})
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        name = user.get('name')
        existing_feedback = feedback_collection.find_one({"name": name})
        if existing_feedback:
            return jsonify({"status": "success"}),201
        if not name:
            return jsonify({"status": "error", "message": "User name not found"}), 404

        # Add name and email to feedback data
        data['name'] = name


        # Insert data into MongoDB
        result = feedback_collection.insert_one(data)
        if result.inserted_id:
            return jsonify({"status": "success", "id": str(result.inserted_id)}), 201
        else:
            return jsonify({"status": "error", "message": "Failed to insert data"}), 500
    except Exception as e:
        # Log the exception details
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
@app.route('/get_feedback', methods=['GET'])
def get_feedback():
    try:
        # Retrieve all feedback
        feedback = feedback_collection.find().sort([('_id', -1)])
        return dumps(feedback)
    except Exception as e:
        # Log the exception details
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



if __name__ == '__main__':
    app.run(debug=True)