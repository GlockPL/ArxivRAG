import streamlit as st

# from rag_pipeline import RAG
from rag_functions import create_graph, stream

def streamlit_app():
    # rag = RAG()
    graph = create_graph()
    st.title("Arxiv cs_AI RAG")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask here question about Arxiv article in cs_AI category?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            token = stream(graph, prompt)
            response = st.write_stream(token)
        st.session_state.messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    streamlit_app()