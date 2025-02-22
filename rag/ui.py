import streamlit as st

from rag_functions import create_graph, stream


def streamlit_app():
    st.title("⚗️ ARXIV cs.AI RAG 🤖")

    if "graph" not in st.session_state:
        st.session_state.graph = create_graph()
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

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
