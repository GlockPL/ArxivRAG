from datetime import datetime

import streamlit as st

from rag_functions import create_graph, stream
from db import PostgresDB

def streamlit_app():
    post_db = PostgresDB()
    st.title("⚗️ ARXIV cs.AI RAG 🤖")

    if "graph" not in st.session_state:
        st.session_state.graph = create_graph()
    if "messages" not in st.session_state:
        st.session_state.messages = []

    with st.sidebar:
        st.title("Chat History")

        # Get all thread IDs
        thread_history = post_db.list_history()
        post_db.close()

        # Add a "New Chat" button
        if st.button("New Chat", key="new_chat"):
            new_thread_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.session_state.current_thread_id = new_thread_id
            st.rerun()

        # st.write(f"Current chat: {}")
        st.write("---")  # Divider
        st.write("Previous Conversations:")

        # Display each thread as a clickable link
        for thread_id in thread_history:
            # Create a clickable link for each conversation
            # The query parameter will be available as st.query_params.thread_id
            st.markdown(f'<a href="?thread_id={thread_id}" target="_self">Conversation {thread_id[:8]}...</a>',
                        unsafe_allow_html=True)

    config = {"configurable": {"thread_id": "1"}}
    state_history = list(st.session_state.graph.get_state_history(config))
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


    # for message in st.session_state.messages:
    #     with st.chat_message(message["role"]):
    #         st.markdown(message["content"])

    if prompt := st.chat_input("Ask here question about Arxiv article in cs.AI category? 😎"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            token = stream(st.session_state.graph, prompt)
            response = st.write_stream(token)
        st.session_state.messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    streamlit_app()
