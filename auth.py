"""ShopiFlow authentication: PostgreSQL-backed accounts and bcrypt password hashing."""
import re
import bcrypt
import streamlit as st
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from config.database import SessionLocal

DUMMY_HASH = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt(rounds=12))


def initialize_auth_table():
    """Create the account table. The DB user needs CREATE permission for first run."""
    db = SessionLocal()
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS shopiflow_users (
                user_id BIGSERIAL PRIMARY KEY,
                full_name VARCHAR(120) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'staff'
                    CHECK (role IN ('admin', 'manager', 'staff')),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def normalize_email(email):
    return (email or "").strip().lower()


def valid_email(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or ""))


def register_user(full_name, email, password):
    full_name = (full_name or "").strip()
    email = normalize_email(email)
    if not full_name or len(full_name) > 120:
        return False, "Enter a name of 1–120 characters."
    if not valid_email(email) or len(email) > 255:
        return False, "Enter a valid email address."
    if len(password or "") < 12:
        return False, "Use a password with at least 12 characters."
    if len(password.encode("utf-8")) > 72:
        return False, "Password must be no longer than 72 UTF-8 bytes."

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")

    db = SessionLocal()
    try:
        db.execute(text("""
            INSERT INTO shopiflow_users (full_name, email, password_hash, role)
            VALUES (:name, :email, :password_hash, 'staff')
        """), {"name": full_name, "email": email, "password_hash": password_hash})
        db.commit()
        return True, "Account created. You can now sign in."
    except IntegrityError:
        db.rollback()
        return False, "An account with that email may already exist."
    except Exception:
        db.rollback()
        return False, "Registration failed. Check the database connection or contact an administrator."
    finally:
        db.close()


def authenticate_user(email, password):
    email = normalize_email(email)
    if not email or not password or len(password.encode("utf-8")) > 72:
        return None
    db = SessionLocal()
    try:
        user = db.execute(text("""
            SELECT user_id, full_name, email, password_hash, role, is_active
            FROM shopiflow_users WHERE email = :email LIMIT 1
        """), {"email": email}).mappings().first()

        stored_hash = user["password_hash"].encode("utf-8") if user else DUMMY_HASH
        try:
            valid = bcrypt.checkpw(password.encode("utf-8"), stored_hash)
        except (ValueError, TypeError):
            valid = False

        if not user or not user["is_active"] or not valid:
            return None
        return {
            "user_id": int(user["user_id"]),
            "full_name": user["full_name"],
            "email": user["email"],
            "role": user["role"],
        }
    finally:
        db.close()


def logout():
    for key in ("authenticated", "shopiflow_user"):
        st.session_state.pop(key, None)
    st.rerun()


def require_login():
    """Render the sign-in/registration gate. Returns True only after login."""
    try:
        initialize_auth_table()
    except Exception as exc:
        st.error("ShopiFlow authentication could not connect to its database.")
        st.info("Check DATABASE_URL / PostgreSQL credentials and database permissions.")
        with st.expander("Technical details"):
            st.code(str(exc)[:1200])
        return False

    if st.session_state.get("authenticated") is True and st.session_state.get("shopiflow_user"):
        return True

    st.markdown("""
    <div class="auth-brand">
      <div class="auth-eyebrow">RETAIL OPERATIONS PLATFORM</div>
      <h1>ShopiFlow</h1>
      <p>Business intelligence, inventory and sales in one workspace.</p>
    </div>
    """, unsafe_allow_html=True)

    _, center, _ = st.columns([1, 1.15, 1])
    with center:
        login_tab, register_tab = st.tabs(["Sign in", "Create account"])
        with login_tab:
            st.subheader("Welcome back")
            st.caption("Sign in with your registered work email.")
            with st.form("shopiflow_login_form"):
                email = st.text_input("Work email", placeholder="name@company.com")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Sign in", type="primary", use_container_width=True)
            if submit:
                user = authenticate_user(email, password)
                if user:
                    st.session_state["shopiflow_user"] = user
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Sign-in failed. Check your credentials or contact your administrator.")

        with register_tab:
            st.subheader("Create an account")
            st.caption("New accounts receive Staff access. Admin access must be assigned separately.")
            with st.form("shopiflow_register_form", clear_on_submit=False):
                full_name = st.text_input("Full name")
                new_email = st.text_input("Work email", placeholder="name@company.com")
                new_password = st.text_input("Password", type="password", help="At least 12 characters.")
                confirm = st.text_input("Confirm password", type="password")
                create = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if create:
                if new_password != confirm:
                    st.error("Passwords do not match.")
                else:
                    ok, message = register_user(full_name, new_email, new_password)
                    if ok:
                        st.success(message)
                    else:
                        st.error(message)

    st.caption("Authorized users only. Registration does not grant administrator privileges.")
    return False
