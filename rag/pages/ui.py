from datetime import datetime
import random
import streamlit as st

from rag.rag_pipeline import RAG
from rag.db.db import PostgresDB
from rag.login import validate_token, get_token_from_cookie, remove_token


def generate_thread_id() -> str:
    new_thread_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"id_{new_thread_id}_{random.randint(0, 100000)}"

def check_access():
    if "access_token" not in st.session_state:
        token = get_token_from_cookie()
        if token:
            if validate_token(token):
                st.session_state.access_token = token
            else:
                print("Access denied: Invalid token in cookie")
                st.session_state.access_token = None
                remove_token()
                st.switch_page("login.py")
        else:
            print("Access denied: token not in cookies")
            st.session_state.access_token = None
            st.switch_page("login.py")

def check_session_access():
    if st.session_state.access_token:
        token = st.session_state.access_token
        if not validate_token(token):
            print("Access denied: invalid token is session")
            st.session_state.access_token = None
            remove_token()
            st.switch_page("login.py")

def streamlit_app():

    check_access()
    check_session_access()

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
        st.markdown(f'<a href="./login?logout=true" target="_self" style="text-decoration:none">Logout</a>', unsafe_allow_html=True)
        st.title("Chat History")
        if st.button("New Chat", key="new_chat"):
            del st.session_state.current_thread_id
            st.switch_page("pages/ui.py")

        # st.markdown(f'<a href="./" target="_self" style="text-decoration:none">New Chat</a>', unsafe_allow_html=True)

        # st.write(f"Current chat: {}")
        st.write("---")  # Divider
        st.write("Previous Conversations:")

        # Display each thread as a clickable link
        for thread_id, thread_title in thread_history.items():
            st.markdown(f'<a href="ui?thread_id={thread_id}" target="_self" style="text-decoration:none">{thread_title}</a>',
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


if __name__ == "__main__":
    streamlit_app()
