from datetime import date, datetime
from functools import wraps
from pathlib import Path
import os
import re

from admin import ensure_admin_account

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func, or_
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
db = SQLAlchemy()
csrf = CSRFProtect()


# Database models for accounts, exercise plans, progress logs, and appointments.
# Database model for account credentials, role, approval, instructor link, and private notes.
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(40), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # instructor / patient
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True)
    approved = db.Column(db.Boolean, default=True, nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    instructor = db.relationship('User', remote_side=[id], backref='patients')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    instructor_notes = db.Column(db.Text)

# Database model for an exercise in the shared exercise library.
class Exercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(60), nullable=False, default='General')
    description = db.Column(db.Text)

# Database model for an exercise assigned to a patient, including its targets.
class ExercisePlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercise.id'), nullable=False)
    duration_minutes = db.Column(db.Integer)
    frequency_per_week = db.Column(db.Integer, nullable=False, default=3)
    sets = db.Column(db.Integer, nullable=False, default=3)
    reps = db.Column(db.Integer, nullable=False, default=10)
    instructions = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient = db.relationship('User', foreign_keys=[patient_id], backref='plans')
    instructor = db.relationship('User', foreign_keys=[instructor_id])
    exercise = db.relationship('Exercise')

# Database model for a patient's completed exercise activity.
class ProgressLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('exercise_plan.id'), nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    sets_completed = db.Column(db.Integer, nullable=False)
    reps_completed = db.Column(db.Integer, nullable=False)
    duration_minutes = db.Column(db.Integer)
    notes = db.Column(db.Text)
    plan = db.relationship('ExercisePlan')
    patient = db.relationship('User')

# Database model for an appointment request between two linked users.
class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    selected_slot_id = db.Column(db.Integer, db.ForeignKey('appointment_slot.id'))
    requester = db.relationship('User', foreign_keys=[requester_id])
    recipient = db.relationship('User', foreign_keys=[recipient_id])
    slots = db.relationship('AppointmentSlot', backref='appointment', cascade='all, delete-orphan', foreign_keys='AppointmentSlot.appointment_id')
    selected_slot = db.relationship('AppointmentSlot', foreign_keys=[selected_slot_id], post_update=True)

# Database model for one proposed appointment date and time.
class AppointmentSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'), nullable=False)
    starts_at = db.Column(db.DateTime, nullable=False)


# Builds the Flask application, registers routes/extensions, and initializes the database.
def create_app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.environ.get('MOTION_SECRET_KEY', 'local-dev-change-this-key'),
                      SQLALCHEMY_DATABASE_URI=f"sqlite:///{INSTANCE_DIR / 'database.db'}",
                      SQLALCHEMY_TRACK_MODIFICATIONS=False)
    db.init_app(app); csrf.init_app(app)

    # Makes the current user and CSRF token helper available to all templates.
    @app.context_processor
    def inject_globals():
        return {'current_user': logged_in(), 'csrf_token': __import__('flask_wtf.csrf', fromlist=['generate_csrf']).generate_csrf}

    # Checks the required ID format: starts with a letter, followed by up to nine letters or digits.
    def valid_user_id(value):
        return bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,9}', value or ''))

    # Checks that a password is exactly six characters long.
    def valid_password(value):
        return len(value or '') == 6

    # Returns the database account stored in the current session, or None if signed out.
    def logged_in():
        return db.session.get(User, session.get('user_id')) if session.get('user_id') else None
    # Used by the template context processor and route guards.
    app.jinja_env.globals['get_user'] = logged_in

    # Decorator that redirects users to login when they are not authenticated.
    def login_required(fn):
        # Checks the signed-in user's role before calling the original route.
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not logged_in(): return redirect(url_for('login'))
            return fn(*args, **kwargs)
        return wrapper
    # Decorator factory that restricts a route to a specified role.
    def role_required(role):
        # Applies authentication and role restrictions to the decorated route.
        def deco(fn):
            # Checks the signed-in user's role before calling the original route.
            @wraps(fn)
            @login_required
            def wrapper(*args, **kwargs):
                if logged_in().role != role: abort(403)
                return fn(*args, **kwargs)
            return wrapper
        return deco
    # Shortcut for retrieving the currently signed-in user.
    def me(): return logged_in()
    # Checks that a patient exists and belongs to the current instructor.
    def owns_patient(patient_id):
        p = db.session.get(User, patient_id)
        if not p or p.role != 'patient' or p.instructor_id != me().id: abort(404)
        return p
    # Checks that the current user and another user are an assigned instructor-patient pair.
    def linked_pair(other):
        u = me()
        if u.role == 'instructor':
            if other.role != 'patient' or other.instructor_id != u.id: abort(404)
        elif other.id != u.instructor_id or other.role != 'instructor': abort(404)

    # Removes dependent records before deleting an account to avoid orphaned database rows.
    def delete_user_records(user):
        """Delete dependent records before deleting an account to avoid orphaned rows.

        This helper is used only after the route has checked the caller's role and
        ownership. It removes progress, plans, appointments, and appointment slots.
        """
        # An instructor deletion also removes their linked patients and all patient data.
        patient_ids = [p.id for p in User.query.filter_by(role='patient', instructor_id=user.id).all()] if user.role == 'instructor' else []
        account_ids = [user.id] + patient_ids
        plan_ids = [row.id for row in ExercisePlan.query.filter(
            or_(ExercisePlan.patient_id.in_(account_ids), ExercisePlan.instructor_id == user.id)
        ).all()]

        if plan_ids:
            ProgressLog.query.filter(ProgressLog.plan_id.in_(plan_ids)).delete(synchronize_session=False)
        ProgressLog.query.filter(ProgressLog.patient_id.in_(account_ids)).delete(synchronize_session=False)
        ExercisePlan.query.filter(ExercisePlan.id.in_(plan_ids)).delete(synchronize_session=False)

        # Delete appointments as ORM objects so their slot relationship cascades cleanly.
        appointments_to_delete = Appointment.query.filter(
            or_(Appointment.requester_id.in_(account_ids), Appointment.recipient_id.in_(account_ids))
        ).all()
        for appointment in appointments_to_delete:
            db.session.delete(appointment)

        for patient_id in patient_ids:
            patient = db.session.get(User, patient_id)
            if patient:
                db.session.delete(patient)
        db.session.delete(user)
        db.session.commit()

    # Redirects to the dashboard if signed in, otherwise to login.
    # AUTHENTICATION: entry point, login, logout, and patient registration.
    @app.route('/')
    def index(): return redirect(url_for('dashboard') if me() else url_for('login'))

    # Checks credentials and approval status, then creates the user's login session.
    @app.route('/login', methods=['GET','POST'])
    def login():
        if me(): return redirect(url_for('dashboard'))
        if request.method == 'POST':
            uid=request.form.get('user_id','').strip(); pw=request.form.get('password','')
            user=User.query.filter_by(user_id=uid).first()
            if not user or not check_password_hash(user.password_hash,pw): flash('Invalid ID or password.','error')
            elif not user.approved: flash('Your account is waiting for instructor approval.','error')
            else:
                session.clear(); session['user_id']=user.id
                return redirect(url_for('dashboard'))
        return render_template('login.html')

    # Ends the current login session.
    @app.route('/logout', methods=['POST'])
    @login_required
    def logout(): session.clear(); return redirect(url_for('login'))

    # Handles patient self-registration and sends the request to the selected instructor for approval.
    @app.route('/register', methods=['GET','POST'])
    def register():
        instructors=User.query.filter_by(role='instructor',approved=True).order_by(User.name).all()
        if request.method=='POST':
            uid=request.form.get('user_id','').strip(); name=request.form.get('name','').strip(); email=request.form.get('email','').strip() or None
            pw=request.form.get('password',''); instructor_id=request.form.get('instructor_id','')
            instructor=db.session.get(User,int(instructor_id)) if instructor_id.isdigit() else None
            if not all([uid,name,pw,instructor]) or not valid_user_id(uid) or not valid_password(pw) or instructor.role!='instructor': flash('Enter a valid user ID (1–10 letters/numbers, starting with a letter) and a 6-character password.','error')
            elif User.query.filter(or_(User.user_id==uid, User.email==email if email else False)).first(): flash('That user ID or email is already registered.','error')
            else:
                user=User(user_id=uid,name=name,email=email,password_hash=generate_password_hash(pw),role='patient',approved=False,instructor=instructor)
                db.session.add(user); db.session.commit(); flash('Registration submitted. Log in after your instructor approves it.','success'); return redirect(url_for('login'))
        return render_template('register.html', instructors=instructors)

    # DASHBOARDS: each role receives a different view and role-appropriate data.
    # Role-specific dashboards keep instructor and patient workflows separate.
    # Routes each account role to its own dashboard and retrieves the relevant summary data.
    @app.route('/dashboard')
    @login_required
    def dashboard():
        u=me()
        if u.role=='admin': return redirect(url_for('admin_dashboard'))
        if u.role=='instructor':
            patients=User.query.filter_by(role='patient',instructor_id=u.id,approved=True).order_by(User.name).all()
            pending=User.query.filter_by(role='patient',instructor_id=u.id,approved=False).count()
            plans=ExercisePlan.query.filter_by(instructor_id=u.id,active=True).count()
            appts=Appointment.query.filter_by(recipient_id=u.id,status='pending').count()
            return render_template('instructor_dashboard.html',patients=patients,pending=pending,plans=plans,appts=appts)
        plans=ExercisePlan.query.filter_by(patient_id=u.id,active=True).all()
        logs=ProgressLog.query.filter_by(patient_id=u.id).order_by(ProgressLog.completed_at.desc()).limit(8).all()
        appts=Appointment.query.filter(or_(Appointment.requester_id==u.id,Appointment.recipient_id==u.id)).order_by(Appointment.created_at.desc()).limit(5).all()
        return render_template('patient_dashboard.html',plans=plans,logs=logs,appointments=appts)

    # Loads all instructor and patient accounts for the administrator.
    # ADMIN: account creation, editing, password resets, and instructor deletion.
    @app.route('/admin')
    @role_required('admin')
    def admin_dashboard():
        # Admin can browse both account groups; passwords are never retrievable.
        instructors = User.query.filter_by(role='instructor').order_by(User.name).all()
        patients = User.query.filter_by(role='patient').order_by(User.name).all()
        return render_template('admin_dashboard.html', instructors=instructors, patients=patients)

    # Updates account identity fields and optionally replaces the password hash.
    @app.route('/admin/users/<int:user_id>/edit', methods=['POST'])
    @role_required('admin')
    def admin_edit_user(user_id):
        """Update account identity fields and optionally reset its password."""
        user = db.get_or_404(User, user_id)
        if user.role not in ('instructor', 'patient'):
            abort(404)  # The built-in admin account cannot be edited from this screen.
        uid = request.form.get('user_id', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip() or None
        new_password = request.form.get('password', '')
        duplicate = User.query.filter(User.id != user.id, or_(
            User.user_id == uid, User.email == email if email else False
        )).first()
        if not valid_user_id(uid) or not name:
            flash('Use a valid user ID (1–10 letters/numbers starting with a letter) and a name.', 'error')
        elif duplicate:
            flash('That user ID or email is already in use.', 'error')
        elif new_password and not valid_password(new_password):
            flash('A new password must contain exactly 6 characters.', 'error')
        else:
            user.user_id, user.name, user.email = uid, name, email
            if new_password:
                user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('Account updated. Password was reset.' if new_password else 'Account updated.', 'success')
        return redirect(url_for('admin_dashboard'))

    # Deletes an instructor and all linked patient accounts and dependent records.
    @app.route('/admin/instructors/<int:user_id>/delete', methods=['POST'])
    @role_required('admin')
    def admin_delete_instructor(user_id):
        """Remove an instructor and their linked patients and dependent records."""
        instructor = db.get_or_404(User, user_id)
        if instructor.role != 'instructor':
            abort(404)
        delete_user_records(instructor)
        flash('Instructor and their linked patient accounts were deleted.', 'success')
        return redirect(url_for('admin_dashboard'))

    # Creates an instructor account after validating the submitted fields.
    @app.route('/admin/instructors/new', methods=['POST'])
    @role_required('admin')
    def admin_create_instructor():
        uid=request.form.get('user_id','').strip()
        name=request.form.get('name','').strip()
        password=request.form.get('password','')
        email=request.form.get('email','').strip() or None
        if not valid_user_id(uid) or not name or not valid_password(password):
            flash('Use a user ID of 1–10 letters/numbers starting with a letter, a name, and a 6-character password.','error')
        elif User.query.filter(or_(User.user_id==uid, User.email==email if email else False)).first():
            flash('That user ID or email is already registered.','error')
        else:
            db.session.add(User(user_id=uid,name=name,email=email,password_hash=generate_password_hash(password),role='instructor',approved=True))
            db.session.commit()
            flash('Instructor account created.','success')
        return redirect(url_for('admin_dashboard'))

    # PATIENT MANAGEMENT: instructor routes are limited to their own assigned patients.
    # Instructor patient management: each instructor can access only their own patients.
    # Lists the current instructor's approved patients and pending registration requests.
    @app.route('/patients')
    @role_required('instructor')
    def patients():
        q=request.args.get('q','').strip()
        query=User.query.filter_by(role='patient',instructor_id=me().id,approved=True)
        if q: query=query.filter(User.name.ilike(f'%{q}%'))
        return render_template('patients.html',patients=query.order_by(User.name).all(),q=q,
                               pending=User.query.filter_by(role='patient',instructor_id=me().id,approved=False).order_by(User.created_at).all())

    # Creates a patient account directly under the current instructor.
    @app.route('/patients/new',methods=['GET','POST'])
    @role_required('instructor')
    def patient_new():
        if request.method=='POST':
            uid=request.form.get('user_id','').strip(); name=request.form.get('name','').strip(); pw=request.form.get('password',''); email=request.form.get('email','').strip() or None
            if not valid_user_id(uid) or not name or not valid_password(pw): flash('Enter a valid user ID (1–10 letters/numbers, starting with a letter), name, and a 6-character password.','error')
            elif User.query.filter(or_(User.user_id==uid,User.email==email if email else False)).first(): flash('User ID or email already exists.','error')
            else:
                p=User(user_id=uid,name=name,email=email,password_hash=generate_password_hash(pw),role='patient',approved=True,instructor_id=me().id)
                db.session.add(p); db.session.commit(); flash('Patient account created.','success'); return redirect(url_for('patients'))
        return render_template('patient_form.html')

    # Approves a patient's pending self-registration.
    @app.route('/patients/<int:pid>/approve',methods=['POST'])
    @role_required('instructor')
    def patient_approve(pid):
        p=owns_patient(pid); p.approved=True; db.session.commit(); flash('Patient approved.','success'); return redirect(url_for('patients'))

    # Deletes one of the current instructor's patients and associated records.
    @app.route('/patients/<int:pid>/delete', methods=['POST'])
    @role_required('instructor')
    def patient_delete(pid):
        """Allow an instructor to delete only a patient assigned to them."""
        patient = owns_patient(pid)
        delete_user_records(patient)
        flash('Patient account and associated records deleted.', 'success')
        return redirect(url_for('patients'))

    # Loads a patient's profile, exercise plans, and recent progress history.
    @app.route('/patients/<int:pid>')
    @role_required('instructor')
    def patient_detail(pid):
        p=owns_patient(pid)
        plans=ExercisePlan.query.filter_by(patient_id=p.id).order_by(ExercisePlan.active.desc(),ExercisePlan.created_at.desc()).all()
        logs=ProgressLog.query.filter_by(patient_id=p.id).order_by(ProgressLog.completed_at.desc()).limit(30).all()
        return render_template('patient_detail.html',patient=p,plans=plans,logs=logs)

    # Saves instructor-only notes on a patient's profile.
    @app.route('/patients/<int:pid>/notes',methods=['POST'])
    @role_required('instructor')
    def patient_notes(pid):
        p=owns_patient(pid); p.instructor_notes=request.form.get('notes','').strip() or None; db.session.commit(); flash('Instructor notes saved.','success'); return redirect(url_for('patient_detail',pid=pid))

    # Loads and displays the exercise library.
    # EXERCISE LIBRARY: browse, add, edit, and delete exercise definitions.
    @app.route('/exercises')
    @login_required
    def exercises():
        items=Exercise.query.order_by(Exercise.category,Exercise.name).all()
        return render_template('exercises.html',exercises=items)

    # Adds a new exercise after checking for a duplicate name.
    @app.route('/exercises/new',methods=['GET','POST'])
    @role_required('instructor')
    def exercise_new():
        if request.method=='POST':
            name=request.form.get('name','').strip(); cat=request.form.get('category','General').strip() or 'General'; desc=request.form.get('description','').strip() or None
            if not name: flash('Exercise name is required.','error')
            elif Exercise.query.filter(func.lower(Exercise.name)==name.lower()).first(): flash('Exercise already exists.','error')
            else: db.session.add(Exercise(name=name,category=cat,description=desc)); db.session.commit(); flash('Exercise added.','success'); return redirect(url_for('exercises'))
        return render_template('exercise_form.html',exercise=None)

    # Updates an existing exercise's information.
    @app.route('/exercises/<int:eid>/edit',methods=['GET','POST'])
    @role_required('instructor')
    def exercise_edit(eid):
        e=db.get_or_404(Exercise,eid)
        if request.method=='POST':
            name=request.form.get('name','').strip(); cat=request.form.get('category','General').strip() or 'General'
            if not name: flash('Exercise name is required.','error')
            else: e.name=name; e.category=cat; e.description=request.form.get('description','').strip() or None; db.session.commit(); flash('Exercise updated.','success'); return redirect(url_for('exercises'))
        return render_template('exercise_form.html',exercise=e)

    # Deletes an exercise only if no plan references it.
    @app.route('/exercises/<int:eid>/delete',methods=['POST'])
    @role_required('instructor')
    def exercise_delete(eid):
        e=db.get_or_404(Exercise,eid)
        if ExercisePlan.query.filter_by(exercise_id=e.id).first(): flash('Exercise is used in an exercise plan and cannot be deleted.','error')
        else: db.session.delete(e); db.session.commit(); flash('Exercise deleted.','success')
        return redirect(url_for('exercises'))

    # Creates an exercise plan for a patient assigned to the current instructor.
    # PLANS AND PROGRESS: instructors assign plans; patients log their own activity.
    @app.route('/plans/new/<int:pid>',methods=['GET','POST'])
    @role_required('instructor')
    def plan_new(pid):
        p=owns_patient(pid); items=Exercise.query.order_by(Exercise.category,Exercise.name).all()
        if request.method=='POST':
            try:
                e=db.get_or_404(Exercise,int(request.form.get('exercise_id'))); sets=int(request.form.get('sets')); reps=int(request.form.get('reps')); freq=int(request.form.get('frequency')); dur=request.form.get('duration','').strip(); dur=int(dur) if dur else None
                if min(sets,reps,freq)<1 or freq>7 or (dur is not None and dur<1): raise ValueError
                plan=ExercisePlan(patient=p,instructor=me(),exercise=e,sets=sets,reps=reps,frequency_per_week=freq,duration_minutes=dur,instructions=request.form.get('instructions','').strip() or None)
                db.session.add(plan); db.session.commit(); flash('Exercise assigned.','success'); return redirect(url_for('patient_detail',pid=pid))
            except (ValueError,TypeError): flash('Check exercise and plan values.','error')
        return render_template('plan_form.html',patient=p,exercises=items)

    # Changes whether an instructor's exercise plan is active.
    @app.route('/plans/<int:plan_id>/toggle',methods=['POST'])
    @role_required('instructor')
    def plan_toggle(plan_id):
        plan=db.get_or_404(ExercisePlan,plan_id)
        if plan.instructor_id!=me().id: abort(404)
        plan.active=not plan.active; db.session.commit(); return redirect(url_for('patient_detail',pid=plan.patient_id))

    # Lets a patient record completion details for their own active exercise plan.
    @app.route('/progress/log/<int:plan_id>',methods=['GET','POST'])
    @role_required('patient')
    def progress_log(plan_id):
        plan=db.get_or_404(ExercisePlan,plan_id)
        if plan.patient_id!=me().id or not plan.active: abort(404)
        if request.method=='POST':
            try:
                sets=int(request.form.get('sets')); reps=int(request.form.get('reps')); dur=request.form.get('duration','').strip(); dur=int(dur) if dur else None
                if min(sets,reps)<1 or (dur is not None and dur<1): raise ValueError
                db.session.add(ProgressLog(patient=me(),plan=plan,sets_completed=sets,reps_completed=reps,duration_minutes=dur,notes=request.form.get('notes','').strip() or None)); db.session.commit(); flash('Progress saved.','success'); return redirect(url_for('dashboard'))
            except ValueError: flash('Enter valid completed sets, reps, and duration.','error')
        return render_template('progress_form.html',plan=plan)

    # APPOINTMENTS: request times, approve, decline, counter-propose, or cancel.
    # Appointment requests are shared between the two linked accounts.
    # Lists appointment requests where the current user is either requester or recipient.
    @app.route('/appointments')
    @login_required
    def appointments():
        u=me(); items=Appointment.query.filter(or_(Appointment.requester_id==u.id,Appointment.recipient_id==u.id)).order_by(Appointment.created_at.desc()).all()
        partner=(u.instructor if u.role=='patient' else None)
        return render_template('appointments.html',appointments=items,partner=partner)

    # Creates an appointment request containing one or more future available time slots.
    @app.route('/appointments/new',methods=['GET','POST'])
    @login_required
    def appointment_new():
        u=me()
        partner=u.instructor if u.role=='patient' else None
        if u.role=='instructor':
            pid=request.args.get('patient_id',''); partner=db.session.get(User,int(pid)) if pid.isdigit() else None
            if partner and (partner.role!='patient' or partner.instructor_id!=u.id or not partner.approved): abort(404)
        if request.method=='POST':
            partner_id=request.form.get('partner_id',''); partner=db.session.get(User,int(partner_id)) if partner_id.isdigit() else partner
            if not partner: flash('Select a valid instructor or patient.','error')
            else:
                try: linked_pair(partner)
                except Exception: abort(404)
                values=request.form.getlist('slots'); slots=[]
                for value in values:
                    if value:
                        dt=datetime.fromisoformat(value)
                        if dt>datetime.now(): slots.append(dt)
                if not slots: flash('Add at least one future available time.','error')
                else:
                    a=Appointment(requester=u,recipient=partner,note=request.form.get('note','').strip() or None)
                    db.session.add(a); db.session.flush()
                    for dt in sorted(set(slots)): db.session.add(AppointmentSlot(appointment=a,starts_at=dt))
                    db.session.commit(); flash('Appointment request sent.','success'); return redirect(url_for('appointments'))
        return render_template('appointment_form.html',partner=partner,patients=User.query.filter_by(role='patient',instructor_id=u.id,approved=True).order_by(User.name).all() if u.role=='instructor' else [])

    # Processes the recipient's approval, decline, or alternative-time response.
    @app.route('/appointments/<int:aid>/respond',methods=['POST'])
    @login_required
    def appointment_respond(aid):
        a=db.get_or_404(Appointment,aid); u=me()
        if a.recipient_id!=u.id or a.status!='pending': abort(403)
        action=request.form.get('action')
        if action=='approve':
            slot=db.session.get(AppointmentSlot,int(request.form.get('slot_id','0')))
            if not slot or slot.appointment_id!=a.id: abort(400)
            a.selected_slot=slot; a.status='approved'; db.session.commit(); flash('Appointment confirmed.','success')
        elif action=='decline': a.status='declined'; db.session.commit(); flash('Appointment declined.','success')
        elif action=='counter':
            values=request.form.getlist('slots'); slots=[]
            for value in values:
                if value:
                    dt=datetime.fromisoformat(value)
                    if dt>datetime.now(): slots.append(dt)
            if not slots: flash('Add at least one future alternative time.','error')
            else:
                for s in list(a.slots): db.session.delete(s)
                original_requester_id=a.requester_id
                a.requester_id=u.id; a.recipient_id=original_requester_id
                for dt in sorted(set(slots)): db.session.add(AppointmentSlot(appointment=a,starts_at=dt))
                a.status='pending'; a.selected_slot=None; db.session.commit(); flash('Alternative times sent.','success')
        else: abort(400)
        return redirect(url_for('appointments'))

    # Cancels an appointment involving the current user.
    @app.route('/appointments/<int:aid>/cancel',methods=['POST'])
    @login_required
    def appointment_cancel(aid):
        a=db.get_or_404(Appointment,aid)
        if me().id not in (a.requester_id,a.recipient_id) or a.status not in ('pending','approved'): abort(403)
        a.status='cancelled'; db.session.commit(); return redirect(url_for('appointments'))

    # Flask CLI command for creating an instructor account from the terminal.
    @app.cli.command('create-instructor')
    def create_instructor():
        import click
        uid=click.prompt('Instructor user ID').strip()
        name=click.prompt('Instructor name').strip()
        password=click.prompt('Password',hide_input=True,confirmation_prompt=True)
        if not valid_user_id(uid) or not name or not valid_password(password):
            raise click.ClickException('Use a user ID of 1–10 letters/numbers starting with a letter, a name, and a 6-character password.')
        if User.query.filter_by(user_id=uid).first():
            raise click.ClickException('That user ID already exists.')
        db.session.add(User(user_id=uid,name=name,password_hash=generate_password_hash(password),role='instructor',approved=True))
        db.session.commit()
        click.echo('Instructor account created.')

    # STARTUP: create missing tables, ensure the admin exists, and seed starter exercises.
    with app.app_context():
        db.create_all()
        ensure_admin_account(db, User)
        if Exercise.query.count()==0:
            db.session.add_all([Exercise(name='Squat',category='Strength',description='Lower-body strength exercise.'),Exercise(name='Push-up',category='Strength',description='Upper-body bodyweight exercise.'),Exercise(name='Plank',category='Core',description='Core stability exercise.'),Exercise(name='Walking',category='Cardio',description='Steady-paced walking.')]); db.session.commit()
    return app

app=create_app()
if __name__=='__main__': app.run(debug=True)
