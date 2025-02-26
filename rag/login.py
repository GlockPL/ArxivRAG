import requests
import streamlit as st
import extra_streamlit_components as stx

from rag.settings import LoginSettings, HostSettings

# Initialize cookie manager
login_settings = LoginSettings()
host_settings = HostSettings()

def get_cookie_manager():
    """Get or create a cookie manager singleton"""
    if "cookie_manager" not in st.session_state:
        st.session_state.cookie_manager = stx.CookieManager(key=login_settings.cookie_key)
    return st.session_state.cookie_manager


def get_token_from_cookie():
    """Retrieve token from cookie if it exists"""
    cookie_manager = get_cookie_manager()
    print(cookie_manager.get_all())
    return cookie_manager.get(cookie="access_token")

def validate_token(token):
    """Check if token is valid by calling the API endpoint"""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.post(
            f"{host_settings.http_type}://{host_settings.host}:{host_settings.port}/validate-token",
            headers=headers
        )
        print(f"Token response: {response.json()}")
        return response.status_code == 200
    except:
        print("Token validation failed")
        return False

def login_user(username, password):
    """Get token from FastAPI endpoint"""
    response = requests.post(
        f"{host_settings.http_type}://{host_settings.host}:{host_settings.port}/token",
        data={"username": username, "password": password}
    )

    if response.status_code == 200:
        token_data = response.json()
        st.session_state.access_token = token_data["access_token"]
        # Store token in cookie for persistence across refreshes
        cookie_manager = get_cookie_manager()
        cookie_manager.set("access_token", token_data["access_token"])
        print("All cookies during login:")
        # print(cookie_manager.get("access_token"))
        return True
    return False


def register_user(username, name, email, password):
    """Register a new user via FastAPI endpoint"""
    response = requests.post(
        f"{host_settings.http_type}://{host_settings.host}:{host_settings.port}/register",
        json={"username": username, "name": name, "email": email, "password": password}
    )

    if response.status_code == 200:
        return True, "Registration successful!"
    else:
        error_msg = "Registration failed"
        if response.status_code == 400:
            try:
                error_msg = response.json().get("detail", error_msg)
            except:
                return False, "Error Parsing Response"
        return False, error_msg

def remove_token():
    cookie_manager = get_cookie_manager()
    cookie_manager.delete("access_token")

def login_page():
    """Render the login page"""
    st.title("Login to the Application")

    if st.query_params.get("logout"):
        print("Logout!")
        logout()

    # Check for token in cookie
    if st.session_state.access_token is None:
        token = get_token_from_cookie()
        if token and validate_token(token):
            st.session_state.access_token = token
            st.switch_page("pages/ui.py")

    # Create tabs for login and registration
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:

        if st.session_state.access_token is None:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Login")

                if submit:
                    if login_user(username, password):
                        st.switch_page("pages/ui.py")
                    else:
                        st.error("Invalid username or password")
        else:
            st.switch_page("pages/ui.py")

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
                    success, message = register_user(new_username, new_name, new_email, new_password)
                    if success:
                        st.success(message)
                        st.info("Please switch to the Login tab to login with your new credentials")
                    else:
                        st.error(message)


def logout():
    """Log out the user by clearing session state and cookies"""
    # Clear session state
    st.session_state['access_token'] = None
    cookie_manager = get_cookie_manager()
    cookie_manager.delete("access_token")
    print("Token after logout:")
    print(cookie_manager.get("access_token"))
    # Redirect to login page
    st.switch_page("login.py")


# When this file is run directly, display the login page
if __name__ == "__main__":
    st.set_page_config(page_title="Login", page_icon="🔒")
    # Set up session state
    if "access_token" not in st.session_state:
        st.session_state.access_token = None
    login_page()
