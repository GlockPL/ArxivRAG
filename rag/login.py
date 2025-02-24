import streamlit as st
import streamlit_authenticator as stauth
import extra_streamlit_components as stx

from db import PostgresDB
from settings import LoginSettings


def initialize_session_state():
    """Initialize session state variables if they don't exist"""
    if 'authentication_status' not in st.session_state:
        st.session_state['authentication_status'] = None
    if 'name' not in st.session_state:
        st.session_state['name'] = None
    if 'username' not in st.session_state:
        st.session_state['username'] = None
    if 'logout' not in st.session_state:
        st.session_state['logout'] = None

    # Capture client info
    if 'client_ip' not in st.session_state:
        st.session_state['client_ip'] = 'Unknown'
    if 'client_user_agent' not in st.session_state:
        st.session_state['client_user_agent'] = 'Unknown'

    # Initialize authenticator only once
    if 'authenticator' not in st.session_state:
        pg = PostgresDB()
        if not pg.users_exists():
            pg.init_db()
        # Get users for authentication
        credentials = pg.get_users_from_db()
        pg.close()

        login_settings = LoginSettings()
        st.session_state['authenticator'] = stauth.Authenticate(
            credentials=credentials,
            cookie_name=login_settings.cookie_name,
            key=login_settings.auth_key,  # Add prefix to make key unique
            cookie_expiry_days=login_settings.cookie_expiry_days,
        )


def login_page():
    """Render the login page"""
    st.title("Login to the Application")

    pg = PostgresDB()

    # Use the authenticator from session state instead of creating a new one
    authenticator = st.session_state['authenticator']

    login_settings = LoginSettings()
    # Create a cookie manager with a unique key
    cookie_manager = stx.CookieManager(key=login_settings.cookie_key)


    # Create tabs for login and registration
    tab1, tab2 = st.tabs(["Login", "Register"])


    with tab1:
        authenticator.login("main", "Login")

        if st.session_state['authentication_status']:
            # Log user login
            name = st.session_state['name']
            username = st.session_state['username']
            ip_address = st.session_state.get('client_ip', 'Unknown')
            user_agent = st.session_state.get('client_user_agent', 'Unknown')
            pg.log_user_login(username, ip_address, user_agent)

            st.success(f"Welcome {name}! You are now logged in.")
            st.info("You'll be redirected to the main application.")

            # Create a cookie to persist the login across multiple pages
            cookie_manager.set("auth_status", "authenticated", key="set_auth_status_cookie")
            cookie_manager.set("username", username, key="set_username_cookie")
            cookie_manager.set("name", name, key="set_name_cookie")

            # Redirect button to main app
            if st.button("Go to Dashboard"):
                st.switch_page("ui.py")  # This will navigate to app.py

        elif st.session_state['authentication_status'] is False:
            st.error("Username/password is incorrect")

        elif st.session_state['authentication_status'] is None:
            st.info("Please enter your username and password")

    with tab2:
        with st.form("registration_form"):
            st.subheader("Create New Account")
            new_username = st.text_input("Username", key="reg_username")
            new_name = st.text_input("Full Name", key="reg_name")
            new_email = st.text_input("Email", key="reg_email")
            new_password = st.text_input("Password", type="password", key="reg_password")
            confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")

            submit_button = st.form_submit_button("Register")

            if submit_button:
                if not new_username or not new_name or not new_email or not new_password:
                    st.error("All fields are required")
                elif new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    success, message = pg.add_user(new_username, new_name, new_email, new_password)
                    if success:
                        st.success(message)
                        st.info("Please switch to the Login tab to login with your new credentials")
                    else:
                        st.error(message)
    pg.close()


def check_authentication():
    """Check if user is authenticated using cookies"""
    cookie_manager = stx.CookieManager(key="check_auth_cookie_manager")
    auth_status = cookie_manager.get("auth_status")

    if auth_status == "authenticated":
        username = cookie_manager.get("username")
        name = cookie_manager.get("name")

        # Restore session state from cookies
        st.session_state['authentication_status'] = True
        st.session_state['username'] = username
        st.session_state['name'] = name

        return True

    return False


def logout():
    """Log out the user by clearing session state and cookies"""
    if st.session_state.get('username'):
        pg = PostgresDB()
        pg.log_user_logout(st.session_state['username'])
        pg.close()

    # Clear session state
    st.session_state['authentication_status'] = None
    st.session_state['name'] = None
    st.session_state['username'] = None

    # Clear cookies
    cookie_manager = stx.CookieManager(key="logout_cookie_manager")
    cookie_manager.delete("auth_status")
    cookie_manager.delete("username")
    cookie_manager.delete("name")

    # Redirect to login page
    st.switch_page("login.py")


# When this file is run directly, display the login page
if __name__ == "__main__":
    st.set_page_config(page_title="Login", page_icon="🔒")
    initialize_session_state()
    login_page()