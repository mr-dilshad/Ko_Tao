from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import uuid
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bluereef.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads/courses'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['SECRET_KEY'] = 'blue-reef-secret-123'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- Database Models ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    bookings = db.relationship('Booking', backref='user', lazy=True)
    reward = db.relationship('Reward', backref='user', uselist=False)
    certificates = db.relationship('Certificate', backref='user', lazy=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    certification_body = db.Column(db.String(50), nullable=False) # SSI or PADI
    duration = db.Column(db.String(50))
    price = db.Column(db.Float, nullable=False)
    min_age = db.Column(db.Integer)
    image_url = db.Column(db.String(255))
    display_order = db.Column(db.Integer, default=0)

class Dormitory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_type = db.Column(db.String(100), nullable=False) # e.g. "4-Bed Mixed Dorm", "Private Double"
    price_per_night = db.Column(db.Float, nullable=False)
    total_beds = db.Column(db.Integer, nullable=False)
    available_beds = db.Column(db.Integer, default=0)

class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    discount_percent = db.Column(db.Float, nullable=False)
    valid_from = db.Column(db.DateTime)
    valid_until = db.Column(db.DateTime)
    min_amount = db.Column(db.Float, default=0.0)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    booking_ref = db.Column(db.String(50), unique=True, nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_email = db.Column(db.String(100), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
    dorm_id = db.Column(db.Integer, db.ForeignKey('dormitory.id'), nullable=True)
    check_in_date = db.Column(db.String(50), nullable=True)
    total_price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float, nullable=True)
    coupon_code = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(50), default="Pending Payment")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    course = db.relationship('Course', backref='bookings')
    dorm = db.relationship('Dormitory', backref='bookings')

class Reward(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    customer_email = db.Column(db.String(100), unique=True, nullable=False)
    points = db.Column(db.Integer, default=0)

class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    customer_email = db.Column(db.String(100), nullable=False)
    course_name = db.Column(db.String(100), nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    cert_ref = db.Column(db.String(50), unique=True)

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255))

# --- Routes ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user:
            flash("An account with this email already exists. Please sign in.", "error")
            return redirect(url_for('register'))
            
        new_user = User(
            email=email,
            name=name,
            password=generate_password_hash(password, method='scrypt')
        )
        db.session.add(new_user)
        db.session.commit()
        
        # Initialize or link rewards
        reward = Reward.query.filter_by(customer_email=email).first()
        if reward:
            reward.user_id = new_user.id
        else:
            reward = Reward(user_id=new_user.id, customer_email=email, points=0)
            db.session.add(reward)
            
        # Link past guest bookings to the new user
        past_bookings = Booking.query.filter_by(customer_email=email, user_id=None).all()
        for booking in past_bookings:
            booking.user_id = new_user.id
            
        # Link past certificates to the new user
        past_certs = Certificate.query.filter_by(customer_email=email, user_id=None).all()
        for cert in past_certs:
            cert.user_id = new_user.id
            
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('user_dashboard'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            flash("Invalid email or password. Please try again.", "error")
            return redirect(url_for('login'))
            
        login_user(user, remember=remember)
        
        if user.is_admin:
            return redirect(url_for('admin'))
        return redirect(url_for('user_dashboard'))
        
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def user_dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/')
def home():
    courses = Course.query.order_by(Course.display_order.asc(), Course.id.asc()).all()
    dorms = Dormitory.query.filter(Dormitory.available_beds > 0).all()
    coupons = Coupon.query.all()
    return render_template('index.html', courses=courses, dorms=dorms, coupons=coupons)

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash("Access denied. Administrators only.", "error")
        return redirect(url_for('home'))
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    courses = Course.query.order_by(Course.display_order.asc(), Course.id.asc()).all()
    dorms = Dormitory.query.all()
    coupons = Coupon.query.all()
    
    # Get settings
    points_setting = Setting.query.filter_by(key='points_per_booking').first()
    reward_points = int(points_setting.value) if points_setting else 100
    
    certificates = Certificate.query.all()
    # Create a set of (customer_email, course_name) for easy lookup
    issued_certs = {(c.customer_email, c.course_name) for c in certificates}
    
    return render_template('admin.html', bookings=bookings, courses=courses, dorms=dorms, coupons=coupons, reward_points=reward_points, issued_certs=issued_certs)

@app.route('/admin/settings/update', methods=['POST'])
def update_settings():
    points = request.form.get('reward_points')
    if points:
        setting = Setting.query.filter_by(key='points_per_booking').first()
        if not setting:
            setting = Setting(key='points_per_booking', value=str(points))
            db.session.add(setting)
        else:
            setting.value = str(points)
        db.session.commit()
    return redirect(url_for('admin') + '?tab=settings')
def create_course():
    name = request.form.get('name')
    certification_body = request.form.get('certification_body')
    duration = request.form.get('duration')
    price = request.form.get('price')
    min_age = request.form.get('min_age')
    
    image_url = None
    if 'image' in request.files:
        file = request.files['image']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_url = f"/static/uploads/courses/{filename}"
    
    max_order = db.session.query(db.func.max(Course.display_order)).scalar() or 0
    
    if name and duration and certification_body and price:
        new_course = Course(
            name=name,
            duration=duration,
            certification_body=certification_body,
            price=max(0.0, float(price)),
            min_age=max(0, int(min_age)) if min_age else None,
            display_order=max_order + 1,
            image_url=image_url
        )
        db.session.add(new_course)
        db.session.commit()
    
    return redirect(url_for('admin') + '?tab=courses')

@app.route('/admin/courses/reorder', methods=['POST'])
def reorder_courses():
    data = request.json
    order = data.get('order', [])
    
    for idx, course_id in enumerate(order):
        course = Course.query.get(int(course_id))
        if course:
            course.display_order = idx * 10
            
    db.session.commit()
    return jsonify({"success": True})

@app.route('/admin/courses/<int:course_id>/delete', methods=['POST'])
def delete_course(course_id):
    course = Course.query.get(course_id)
    if course:
        db.session.delete(course)
        db.session.commit()
    return redirect(url_for('admin') + '?tab=courses')

@app.route('/admin/courses/<int:course_id>/edit', methods=['POST'])
def edit_course(course_id):
    course = Course.query.get(course_id)
    if course:
        course.name = request.form.get('name')
        course.duration = request.form.get('duration')
        course.certification_body = request.form.get('certification_body')
        course.price = max(0.0, float(request.form.get('price')))
        min_age = request.form.get('min_age')
        if min_age:
            course.min_age = max(0, int(min_age))
            
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                # Delete old image if exists
                if course.image_url:
                    try:
                        old_path = os.path.join(app.root_path, course.image_url.lstrip('/'))
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    except: pass
                
                filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                course.image_url = f"/static/uploads/courses/{filename}"
                
        db.session.commit()
    return redirect(url_for('admin') + '?tab=courses')

@app.route('/admin/dorms/new', methods=['POST'])
def create_dorm():
    room_type = request.form.get('room_type')
    price_per_night = request.form.get('price_per_night')
    total_beds = request.form.get('total_beds')
    
    if room_type and price_per_night and total_beds:
        total = max(1, int(total_beds))
        new_dorm = Dormitory(
            room_type=room_type,
            price_per_night=max(0.0, float(price_per_night)),
            total_beds=total,
            available_beds=total
        )
        db.session.add(new_dorm)
        db.session.commit()
    
    return redirect(url_for('admin') + '?tab=dormitory')

@app.route('/admin/dorms/<int:dorm_id>/edit', methods=['POST'])
def edit_dorm(dorm_id):
    dorm = Dormitory.query.get(dorm_id)
    if dorm:
        dorm.room_type = request.form.get('room_type')
        dorm.total_beds = max(1, int(request.form.get('total_beds')))
        available_beds = max(0, int(request.form.get('available_beds')))
        dorm.available_beds = available_beds if available_beds <= dorm.total_beds else dorm.total_beds
        dorm.price_per_night = max(0.0, float(request.form.get('price_per_night')))
        db.session.commit()
    return redirect(url_for('admin') + '?tab=dormitory')

@app.route('/admin/dorms/<int:dorm_id>/delete', methods=['POST'])
def delete_dorm(dorm_id):
    dorm = Dormitory.query.get(dorm_id)
    if dorm:
        db.session.delete(dorm)
        db.session.commit()
    return redirect(url_for('admin') + '?tab=dormitory')

@app.route('/admin/bookings/<int:booking_id>/complete', methods=['POST'])
def complete_booking(booking_id):
    booking = Booking.query.get(booking_id)
    if booking and booking.status == "Confirmed":
        booking.status = "Completed"
        if booking.dorm_id:
            dorm = Dormitory.query.get(booking.dorm_id)
            if dorm:
                dorm.available_beds += 1
        db.session.commit()
        
        # Mock Email for Checkout
        print(f"--- MOCK EMAIL ---")
        print(f"To: {booking.customer_email}")
        print(f"Subject: Checkout Complete - BlueReef")
        print(f"Dear {booking.customer_name}, we hope you enjoyed your stay at BlueReef!")
        print(f"Your bed in {booking.dorm.room_type if booking.dorm else 'N/A'} has been released. Safe travels!")
        print(f"------------------")
    return redirect(url_for('admin') + '?tab=bookings')

@app.route('/admin/bookings/<int:booking_id>/issue-cert', methods=['POST'])
@login_required
def issue_cert(booking_id):
    if not current_user.is_admin:
        return redirect(url_for('home'))
        
    booking = Booking.query.get_or_404(booking_id)
    if not booking.course_id:
        flash("This booking is not for a course.", "error")
        return redirect(url_for('admin'))

    # Check if already issued for this email
    existing = Certificate.query.filter_by(customer_email=booking.customer_email, course_name=booking.course.name).first()
    if existing:
        flash("Certificate already issued to this email for this course.", "info")
        return redirect(url_for('admin'))

    # Issue Certificate (linked to user if account exists)
    new_cert = Certificate(
        user_id=booking.user_id,
        customer_email=booking.customer_email,
        course_name=booking.course.name,
        cert_ref=f"BR-{uuid.uuid4().hex[:8].upper()}"
    )
    db.session.add(new_cert)
    db.session.commit()
    
    flash(f"Certificate issued to {booking.customer_name} ({booking.customer_email})!", "success")
    return redirect(url_for('admin'))

@app.route('/admin/coupons/new', methods=['POST'])
def create_coupon():
    code = request.form.get('code')
    discount_percent = request.form.get('discount_percent')
    valid_from_str = request.form.get('valid_from')
    valid_until_str = request.form.get('valid_until')
    min_amount = request.form.get('min_amount')
    
    valid_from_dt = datetime.strptime(valid_from_str, '%Y-%m-%d') if valid_from_str else None
    valid_until_dt = datetime.strptime(valid_until_str, '%Y-%m-%d') if valid_until_str else None
    
    if valid_from_dt and valid_until_dt and valid_until_dt <= valid_from_dt:
        return "Error: End date must be after Start date.", 400

    if code and discount_percent:
        new_coupon = Coupon(
            code=code.upper(),
            discount_percent=max(0.0, min(float(discount_percent), 100.0)),
            min_amount=max(0.0, float(min_amount)) if min_amount else 0.0,
            valid_from=valid_from_dt,
            valid_until=valid_until_dt
        )
        db.session.add(new_coupon)
        db.session.commit()
    
    return redirect(url_for('admin') + '?tab=coupons')

@app.route('/admin/coupons/<int:coupon_id>/delete', methods=['POST'])
def delete_coupon(coupon_id):
    coupon = Coupon.query.get(coupon_id)
    if coupon:
        db.session.delete(coupon)
        db.session.commit()
    return redirect(url_for('admin') + '?tab=coupons')

@app.route('/api/validate-coupon')
def validate_coupon():
    code = request.args.get('code', '').upper()
    check_in_str = request.args.get('check_in', '')
    if not code:
        return jsonify({"valid": False, "error": "No code provided."})
    
    coupon = Coupon.query.filter_by(code=code).first()
    if not coupon:
        return jsonify({"valid": False, "error": "Invalid coupon code."})
    
    # Use check-in date for validation if provided, else use today
    try:
        check_date = datetime.strptime(check_in_str, '%Y-%m-%d').date() if check_in_str else datetime.utcnow().date()
    except ValueError:
        check_date = datetime.utcnow().date()

    if coupon.valid_from and check_date < coupon.valid_from.date():
        return jsonify({"valid": False, "error": f"This coupon is not valid until {coupon.valid_from.strftime('%b %d, %Y')}."})
    if coupon.valid_until and check_date > coupon.valid_until.date():
        return jsonify({"valid": False, "error": "This coupon has expired for your selected check-in date."})
    
    return jsonify({
        "valid": True,
        "discount": coupon.discount_percent,
        "min_amount": coupon.min_amount,
        "message": f"{coupon.discount_percent}% discount applied!"
    })

@app.route('/admin/coupons/<int:coupon_id>/edit', methods=['POST'])
def edit_coupon(coupon_id):
    coupon = Coupon.query.get(coupon_id)
    if not coupon:
        return redirect(url_for('admin') + '?tab=coupons')
        
    code = request.form.get('code')
    discount_percent = request.form.get('discount_percent')
    valid_from_str = request.form.get('valid_from')
    valid_until_str = request.form.get('valid_until')
    min_amount = request.form.get('min_amount')
    
    valid_from_dt = datetime.strptime(valid_from_str, '%Y-%m-%d') if valid_from_str else None
    valid_until_dt = datetime.strptime(valid_until_str, '%Y-%m-%d') if valid_until_str else None
    
    if valid_from_dt and valid_until_dt and valid_until_dt <= valid_from_dt:
        return "Error: End date must be after Start date.", 400

    if code and discount_percent:
        coupon.code = code.upper()
        coupon.discount_percent = max(0.0, min(float(discount_percent), 100.0))
        coupon.min_amount = max(0.0, float(min_amount)) if min_amount else 0.0
        coupon.valid_from = valid_from_dt
        coupon.valid_until = valid_until_dt
        db.session.commit()
    
    return redirect(url_for('admin') + '?tab=coupons')

@app.route('/api/book', methods=['POST'])
def create_booking():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    course_id = data.get('course_id')
    dorm_id = data.get('dorm_id')
    check_in = data.get('check_in_date')
    coupon_code = data.get('coupon_code')
    
    total_price = 0.0
    
    if course_id:
        course = Course.query.get(course_id)
        if course:
            total_price += course.price
            
    if dorm_id:
        dorm = Dormitory.query.get(dorm_id)
        if dorm and dorm.available_beds > 0:
            total_price += dorm.price_per_night
        elif dorm:
            return jsonify({"success": False, "error": "Dorm fully booked"})
            
    if coupon_code:
        coupon = Coupon.query.filter_by(code=coupon_code.upper()).first()
        if not coupon:
            return jsonify({"success": False, "error": "Invalid coupon code."})
        
        # Validate against check-in date, not today's date
        try:
            check_date = datetime.strptime(check_in, '%Y-%m-%d').date() if check_in else datetime.utcnow().date()
        except (ValueError, TypeError):
            check_date = datetime.utcnow().date()

        if coupon.valid_from and check_date < coupon.valid_from.date():
            return jsonify({"success": False, "error": f"This coupon is not valid until {coupon.valid_from.strftime('%b %d, %Y')}."})
        if coupon.valid_until and check_date > coupon.valid_until.date():
            return jsonify({"success": False, "error": "This coupon is not valid for your selected check-in date."})
        if coupon.min_amount and total_price < coupon.min_amount:
            return jsonify({"success": False, "error": f"Minimum order amount of ${coupon.min_amount} is required for this coupon."})
            
        original_price = total_price
        total_price = total_price * (1 - (coupon.discount_percent / 100.0))
        applied_coupon_code = coupon_code.upper()
    else:
        original_price = None
        applied_coupon_code = None
            
    booking_ref = "BR-" + str(uuid.uuid4())[:8].upper()
    
    booking = Booking(
        booking_ref=booking_ref,
        customer_name=name,
        customer_email=email,
        course_id=course_id if course_id else None,
        dorm_id=dorm_id if dorm_id else None,
        check_in_date=check_in,
        total_price=round(total_price, 2),
        original_price=round(original_price, 2) if original_price else None,
        coupon_code=applied_coupon_code,
        status="Pending Payment"
    )
    
    db.session.add(booking)
    db.session.commit()
    
    return jsonify({
        "success": True, 
        "booking_id": booking.id, 
        "booking_ref": booking_ref, 
        "total_price": total_price
    })

@app.route('/api/pay', methods=['POST'])
def process_payment():
    data = request.json
    booking_id = data.get('booking_id')
    booking = Booking.query.get(booking_id)
    
    if not booking or booking.status != "Pending Payment":
        return jsonify({"success": False, "error": "Invalid booking session."})
    
    # Check inventory one last time before confirming
    if booking.dorm_id:
        dorm = Dormitory.query.get(booking.dorm_id)
        if not dorm or dorm.available_beds <= 0:
            return jsonify({"success": False, "error": "Accommodation no longer available."})
        dorm.available_beds -= 1
        
    booking.status = "Confirmed"
    
    # Link to user if logged in
    if current_user.is_authenticated:
        booking.user_id = current_user.id
    
    # Reward System
    reward = Reward.query.filter_by(customer_email=booking.customer_email).first()
    if not reward:
        # Create reward record (linked to user if logged in)
        user_id = current_user.id if current_user.is_authenticated else None
        reward = Reward(user_id=user_id, customer_email=booking.customer_email, points=0)
        db.session.add(reward)
    # Get reward points setting
    points_setting = Setting.query.filter_by(key='points_per_booking').first()
    points_to_add = int(points_setting.value) if points_setting else 100
    
    reward.points += points_to_add
    db.session.commit()
    
    # Mock Email Confirmation
    print(f"--- MOCK EMAIL ---")
    print(f"To: {booking.customer_email}")
    print(f"Subject: Booking Confirmation {booking.booking_ref}")
    print(f"Dear {booking.customer_name}, your booking is confirmed. Total: ${booking.total_price:.2f}. You have earned {points_to_add} reward points!")
    print(f"------------------")
    
    return jsonify({"success": True, "message": "Payment successful and booking confirmed!"})


def init_db():
    with app.app_context():
        db.create_all()
        # Seed Data
        if not Course.query.first():
            db.session.add(Course(name="Try Scuba / Intro Dive", certification_body="SSI", duration="1 Day", price=100.0, min_age=10))
            db.session.add(Course(name="Open Water Diver", certification_body="SSI", duration="3-4 Days", price=350.0, min_age=10))
            db.session.add(Course(name="Advanced Adventurer", certification_body="SSI", duration="2-3 Days", price=300.0, min_age=12))
            
        if not Dormitory.query.first():
            db.session.add(Dormitory(room_type="8-Bed Mixed Dorm", price_per_night=15.0, total_beds=8))
            db.session.add(Dormitory(room_type="4-Bed Female Dorm", price_per_night=20.0, total_beds=4))
            db.session.add(Dormitory(room_type="Private Double Room", price_per_night=60.0, total_beds=1))
            
        if not Coupon.query.first():
            db.session.add(Coupon(code="WELCOME10", discount_percent=10.0))
            
        db.session.commit()

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)
