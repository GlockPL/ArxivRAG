from datetime import datetime

import requests
import streamlit as st
import extra_streamlit_components as stx
import random

from rag.rag_pipeline import RAG
from rag.db.db import PostgresDB
from rag.settings import LoginSettings, HostSettings

# Initialize cookie manager
login_settings = LoginSettings()
host_settings = HostSettings()

cookie_mngr = stx.CookieManager(key=login_settings.cookie_key)

def get_cookie_manager():
    """Get or create a cookie manager singleton"""
    if "cookie_manager" not in st.session_state:
        st.session_state.cookie_manager = stx.CookieManager(key=login_settings.cookie_key)
    return st.session_state.cookie_manager
    # key=login_settings.cookie_key
    # return stx.CookieManager()

def get_token_from_cookie():
    """Retrieve token from cookie if it exists"""
    # cookie_manager = get_cookie_manager()
    return cookie_mngr.get(cookie="access_token")


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
        # cookie_manager = get_cookie_manager()
        cookie_mngr.set("access_token", token_data["access_token"])
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
    # cookie_manager = get_cookie_manager()
    cookie_mngr.delete("access_token")


def login_page():
    """Render the login page"""
    st.title("Login to the Application")

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
                        st.switch_page("streamlit.py")
                    else:
                        st.error("Invalid username or password")
        else:
            st.switch_page("streamlit.py")

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


def generate_thread_id() -> str:
    new_thread_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"id_{new_thread_id}_{random.randint(0, 100000)}"


def check_cookie_access():
    token = get_token_from_cookie()
    print(f"Check access function cookie: {token}")
    print("==================================")
    if token:
        if validate_token(token):
            st.session_state.access_token = token
        else:
            print("Access denied: Invalid token in cookie")
            print("==================================")
            st.session_state.access_token = None
            remove_token()
            return False
    else:
        print("Access denied: token not in cookies")
        print("==================================")
        st.session_state.access_token = None
        return False

    return True


def check_session_access():
    if st.session_state.access_token:
        token = st.session_state.access_token
        if not validate_token(token):
            print("Access denied: invalid token is session")
            print("==================================")
            st.session_state.access_token = None
            remove_token()
            return False
        return True


def ui_page():
    st.write(f"Token in cookies: {get_token_from_cookie()}")
    if "thread_id" in st.query_params:
        st.session_state.current_thread_id = st.query_params["thread_id"]

    if "graph" not in st.session_state:
        st.session_state.rag = RAG()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    post_db = PostgresDB()
    thread_history = []
    if post_db.conversation_titles_exists():
        thread_history = post_db.list_titles()
    post_db.close()

    if "current_thread_id" not in st.session_state:
        st.session_state.current_thread_id = generate_thread_id()
        st.title("⚗️ ARXIV cs.AI RAG 🤖")
    else:
        if st.session_state.current_thread_id in thread_history:
            st.markdown(f"## ⚗️ {thread_history[st.session_state.current_thread_id]}")

    with st.sidebar:
        st.markdown(f'<a href="./?logout=true" target="_self" style="text-decoration:none">Logout</a>',
                    unsafe_allow_html=True)
        st.title("Chat History")
        if st.button("New Chat", key="new_chat"):
            del st.session_state.current_thread_id
            st.switch_page("streamlit.py")

        # st.markdown(f'<a href="./" target="_self" style="text-decoration:none">New Chat</a>', unsafe_allow_html=True)

        # st.write(f"Current chat: {}")
        st.write("---")  # Divider
        st.write("Previous Conversations:")

        # Display each thread as a clickable link
        for thread_id, thread_title in thread_history.items():
            st.markdown(
                f'<a href="./?thread_id={thread_id}" target="_self" style="text-decoration:none">{thread_title}</a>',
                unsafe_allow_html=True)

    config = {"configurable": {"thread_id": st.session_state.current_thread_id}}

    state_history = list(st.session_state.rag.get_state_history(config))
    conversation = []
    if len(state_history) > 0:
        conversation = state_history[0][0]['messages']

    for message in conversation:
        if message.type == "human":
            with st.chat_message("user"):
                st.write(message.content)
        elif message.type == "ai":
            if message.content:
                with st.chat_message("assistant"):
                    st.write(message.content)

    if prompt := st.chat_input("Ask here question about Arxiv article in cs.AI category? 😎"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            # token = stream(st.session_state.graph, prompt, st.session_state.current_thread_id)
            token = st.session_state.rag.stream(prompt, st.session_state.current_thread_id)
            response = st.write_stream(token)
        st.session_state.messages.append({"role": "assistant", "content": response})


def logout():
    """Log out the user by clearing session state and cookies"""
    # Clear session state
    st.session_state['access_token'] = None
    # cookie_manager = get_cookie_manager()
    print("Checking if access token exists")
    if cookie_mngr.get("access_token"):
        print("Deleting access token from cookies")
        cookie_mngr.delete("access_token")
    print("Token after logout:")
    print(cookie_mngr.get("access_token"))
    print("==================================")
    # Redirect to login page
    st.switch_page("streamlit.py")


def route():
    print(f"Session state: {st.session_state}")
    print("==================================")

    if "access_token" not in st.session_state:
        st.session_state.access_token = None

    if check_session_access():
        print("Check session access function returned True.")
        print("==========================================")
        return ui_page()

    if check_cookie_access():
        print("Check access function returned True.")
        return ui_page()

    if st.query_params.get("logout"):
        print("Logout!")
        print("==================================")
        return logout()

    return login_page()


# When this file is run directly, display the login page
if __name__ == "__main__":

    route()