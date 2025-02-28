from datetime import datetime
from typing import List, Dict, Any, Generator

import requests
import streamlit as st
import random
import sseclient
import logging
from streamlit_cookies_controller import CookieController

from rag.rag_pipeline import RAG
from rag.settings import LoginSettings, HostSettings, Settings

# Initialize settings
main_settings = Settings()
login_settings = LoginSettings()
host_settings = HostSettings()

logging.basicConfig(level=main_settings.logging_level)

def get_cookie_manager():
    """Get or create a cookie manager singleton"""
    return CookieController(key=login_settings.cookie_key)

def get_token_from_cookie():
    """Retrieve token from cookie if it exists"""
    cookie_manager = get_cookie_manager()
    return cookie_manager.get("access_token")


def validate_token(token):
    """Check if token is valid by calling the API endpoint"""
    if not token:
        return False

    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.post(
            f"{host_settings.http_type}://{host_settings.host}:{host_settings.port}/validate-token",
            headers=headers
        )
        logging.debug(f"Token response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        logging.debug(f"Token validation failed: {e}")
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

        # Set cookie with more explicit parameters
        cookie_manager = get_cookie_manager()
        cookie_manager.set(
            "access_token",
            token_data["access_token"],
            max_age=60*60*8
        )
        logging.debug(f"COOKIE SET: {cookie_manager.get('access_token')}")
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
    """Remove the access token from both session state and cookies"""
    st.session_state.access_token = None
    cookie_manager = get_cookie_manager()
    cookie_manager.remove("access_token")
    logging.debug(f"Token removed, current cookie value: {cookie_manager.get('access_token')}")


def check_conversation_exists(thread_id):
    """
    Check if a conversation exists and the current user has access to it

    Args:
        thread_id: The thread ID to check

    Returns:
        tuple: (exists, error_message)
            - exists: boolean indicating if conversation exists and is accessible
            - error_message: String with error details if any, None otherwise
    """
    token = st.session_state.get("access_token")
    if not token:
        return False, "Not authenticated"

    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(
            f"{host_settings.http_type}://{host_settings.host}:{host_settings.port}/conversations/{thread_id}",
            headers=headers
        )

        if response.status_code == 200:
            # Conversation exists and user has access
            # You can store the conversation data if needed
            return True, None
        elif response.status_code == 404:
            return False, "Conversation not found"
        elif response.status_code == 403:
            return False, "You don't have permission to access this conversation"
        else:
            return False, f"Error: {response.status_code}"

    except Exception as e:
        logging.debug(f"Error checking conversation: {e}")
        return False, f"Connection error: {str(e)}"


def fetch_conversations() -> list[Any] | None | Any:
    """
    Fetches all conversations for the currently authenticated user.

    Returns:
        List[Dict[str, Any]]: List of conversation objects

    Raises:
        requests.RequestException: If the API request fails
    """
    token = st.session_state.get("access_token")
    if not token:
        st.error(f"Not authenticated!")
        return []
    # Construct the full URL
    url = f"{host_settings.http_type}://{host_settings.host}:{host_settings.port}/conversations/"

    # Set up the request headers
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        # Make the API request
        response = requests.get(url, headers=headers)

        # Raise an exception for HTTP errors
        response.raise_for_status()

        # Parse and return the JSON response
        conversations = response.json()
        return conversations

    except requests.RequestException:
        st.error(f"Failed to fetch conversations")


def fetch_conversation_messages(thread_id: str) -> list[Any] | None | Any:
    """
    Fetches all messages for a specific conversation thread.

    Args:
        base_url (str): The base URL of the API
        auth_token (str): JWT or other authentication token
        thread_id (str): The unique identifier for the conversation thread

    Returns:
        List[Dict[str, Any]]: List of message objects

    Raises:
        requests.RequestException: If the API request fails
    """
    token = st.session_state.get("access_token")
    if not token:
        st.error(f"Not authenticated!")
        return []

    url = f"{host_settings.http_type}://{host_settings.host}:{host_settings.port}/conversations/{thread_id}/messages"

    # Set up the request headers
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        # Make the API request
        response = requests.get(url, headers=headers)

        # Raise an exception for HTTP errors
        response.raise_for_status()

        if response.status_code == 404:
            return []

        # Parse and return the JSON response
        messages = response.json()
        return messages

    except requests.RequestException:
            return []


def stream_conversation_tokens(thread_id: str, query: str) -> Generator[str, None, None]:
    """
    Stream tokens from the conversation streaming endpoint.

    Args:
        thread_id (str): The ID of the conversation thread
        query (str): The user query to process

    Yields:
        str: Each token as it's received from the server

    Raises:
        requests.RequestException: If the API request fails
    """
    token = st.session_state.get("access_token")
    if not token:
        st.error(f"Not authenticated!")
        return None

    url = f"{host_settings.http_type}://{host_settings.host}:{host_settings.port}/conversations/{thread_id}/stream"

    # Set up the request headers
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/plain"
    }

    # Set up query parameters
    params = {"query": query}

    try:
        # Make the streaming request
        with requests.get(url, headers=headers, params=params, stream=True) as response:
            response.raise_for_status()

            # Stream the response content
            for chunk in response.iter_content(chunk_size=1):
                if chunk:
                    yield chunk.decode('utf-8')

    except requests.RequestException as e:
        st.error(f"Failed to stream tokens: {str(e)}")
        yield f"ERROR: {str(e)}"

def login_page():
    """Render the login page"""
    st.title("Login to the Application")

    # Create tabs for login and registration
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        if not st.session_state.get("access_token"):
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Login")

                if submit:
                    if login_user(username, password):
                        st.rerun()  # Use rerun instead of switch_page to ensure cookies are properly set
                    else:
                        st.error("Invalid username or password")
        else:
            st.success("Login successful!")
            st.button("Continue to Application", on_click=lambda: st.rerun())

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


def check_authentication():
    """Unified function to check authentication status"""
    # IMPORTANT: Check cookie FIRST, then session state
    cookie_token = get_token_from_cookie()
    logging.debug(f"Cookie token: {cookie_token}")
    if cookie_token and validate_token(cookie_token):
        # If cookie token is valid, update session state
        st.session_state.access_token = cookie_token
        logging.debug("User authenticated via cookie")
        return True

    # Then try session state as backup
    if st.session_state.get("access_token") and validate_token(st.session_state.access_token):
        cookie_manager = get_cookie_manager()
        cookie_manager.set("access_token", st.session_state.access_token)
        logging.debug("User authenticated via session state")
        return True

    # No valid authentication found
    st.session_state.access_token = None
    logging.debug("User not authenticated")
    return False


def ui_page():
    if "thread_id" in st.query_params:
        st.session_state.current_thread_id = st.query_params["thread_id"]

    if "graph" not in st.session_state:
        st.session_state.rag = RAG()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    thread_history = fetch_conversations()

    if "current_thread_id" not in st.session_state:
        st.session_state.current_thread_id = generate_thread_id()
        st.title("⚗️ ARXIV cs.AI RAG 🤖")
    else:
        if st.session_state.current_thread_id in thread_history:
            st.markdown(f"## ⚗️ {thread_history[st.session_state.current_thread_id]}")
        else:
            st.title("⚗️ ARXIV cs.AI RAG 🤖")

    with st.sidebar:
        # Create a button instead of a link for logout
        if st.button("Logout", key="logout_button"):
            remove_token()
            st.rerun()

        st.title("Chat History")
        if st.button("New Chat", key="new_chat"):
            # Just reset the thread ID, don't switch page
            st.session_state.current_thread_id = generate_thread_id()
            st.rerun()

        st.write("---")  # Divider
        st.write("Previous Conversations:")

        # Use URLs with state params instead of query params
        for row in thread_history:
            thread_id = row["thread_id"]
            thread_title = row["title"]
            if st.button(thread_title, key=f"thread_{thread_id}"):
                st.session_state.current_thread_id = thread_id
                st.rerun()

    conversation = fetch_conversation_messages(thread_id=st.session_state.current_thread_id)
    for message in conversation:
        if message["type"] == "human":
            with st.chat_message("user"):
                st.write(message["content"])
        elif message["type"] == "ai":
            if message["content"]:
                with st.chat_message("assistant"):
                    st.write(message["content"])

    if prompt := st.chat_input("Ask here question about Arxiv article in cs.AI category? 😎"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            response = st.write_stream(stream_conversation_tokens(st.session_state.current_thread_id, prompt))
        st.session_state.messages.append({"role": "assistant", "content": response})


def route():
    logging.debug(f"Session state: {st.session_state}")
    logging.debug(f"Query params: {st.query_params}")
    # Initialize access_token if not present
    if "access_token" not in st.session_state:
        st.session_state.access_token = None

    # Handle logout explicitly
    if st.query_params.get("logout"):
        logging.debug("Logout parameter detected")
        remove_token()
        # Redirect by clearing query params and session state
        st.query_params.clear()
        st.rerun()

    # Check authentication
    if check_authentication():
        return ui_page()
    else:
        return login_page()


# When this file is run directly
if __name__ == "__main__":
    route()
