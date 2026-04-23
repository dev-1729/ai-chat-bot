import streamlit as st
import sqlite3
import os

# ---------------- SECRETS ----------------
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

# ---------------- LOCAL IMPORTS ----------------
from database import init_db
from auth import create_user, login_user

# ---------------- LANGCHAIN ----------------
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

# ---------------- INIT ----------------
init_db()

st.set_page_config(page_title="PDF Chatbot", layout="wide")

# ---------------- SESSION ----------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "chat_id" not in st.session_state:
    st.session_state.chat_id = None

if "db" not in st.session_state:
    st.session_state.db = None

if "llm" not in st.session_state:
    st.session_state.llm = ChatOpenAI(model="gpt-4o-mini")

# ---------------- LOGIN ----------------
if not st.session_state.user_id:
    st.title("🔐 Login / Signup")

    tab1, tab2 = st.tabs(["Login", "Signup"])

    with tab1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            user_id = login_user(username, password)
            if user_id:
                st.session_state.user_id = user_id
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab2:
        new_user = st.text_input("New Username")
        new_pass = st.text_input("New Password", type="password")

        if st.button("Signup"):
            if create_user(new_user, new_pass):
                st.success("Account created! Please login.")
            else:
                st.error("Username already exists")

    st.stop()

# ---------------- SIDEBAR ----------------
st.sidebar.title("💬 Your Chats")

conn = sqlite3.connect("chat.db")
c = conn.cursor()

c.execute("SELECT id, title FROM chats WHERE user_id=?", (st.session_state.user_id,))
chats = c.fetchall()

if st.sidebar.button("➕ New Chat"):
    c.execute(
        "INSERT INTO chats (user_id, title) VALUES (?, ?)",
        (st.session_state.user_id, "New Chat")
    )
    conn.commit()
    st.rerun()

for chat in chats:
    if st.sidebar.button(chat[1], key=chat[0]):
        st.session_state.chat_id = chat[0]

conn.close()

# ---------------- DB FUNCTIONS ----------------
def load_messages(chat_id):
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()

    c.execute("SELECT role, content FROM messages WHERE chat_id=?", (chat_id,))
    data = c.fetchall()
    conn.close()

    return [{"role": r, "content": c} for r, c in data]


def save_message(chat_id, role, content):
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()

    c.execute(
        "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
        (chat_id, role, content)
    )
    conn.commit()
    conn.close()

# ---------------- MAIN ----------------
st.title("📄 Multi-PDF Chatbot")

uploaded_files = st.file_uploader(
    "Upload PDFs",
    type="pdf",
    accept_multiple_files=True
)

# ✅ FIX: always rebuild DB when files uploaded
if uploaded_files:
    all_docs = []

    for i, file in enumerate(uploaded_files):
        file_path = f"/tmp/temp_{i}.pdf"

        with open(file_path, "wb") as f:
            f.write(file.read())

        loader = PyPDFLoader(file_path)
        docs = loader.load()

        for d in docs:
            d.metadata["source"] = file.name

        all_docs.extend(docs)

    splitter = CharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100
    )

    docs = splitter.split_documents(all_docs)

    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2"
    )

    st.session_state.db = FAISS.from_documents(docs, embeddings)

# ---------------- CHAT ----------------
if st.session_state.chat_id and st.session_state.db:

    history = load_messages(st.session_state.chat_id)

    # Display history
    for chat in history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])

    user_input = st.chat_input("Ask something about your PDFs...")

    if user_input:
        save_message(st.session_state.chat_id, "user", user_input)

        with st.chat_message("user"):
            st.markdown(user_input)

        retriever = st.session_state.db.as_retriever(search_kwargs={"k": 4})
        docs = retriever.invoke(user_input)

        context = "\n\n".join([d.page_content for d in docs])

        # Limit memory
        recent_history = history[-6:]

        messages = [
            SystemMessage(content="Answer only using the provided PDF context.")
        ]

        for chat in recent_history:
            if chat["role"] == "user":
                messages.append(HumanMessage(content=chat["content"]))
            else:
                messages.append(AIMessage(content=chat["content"]))

        messages.append(
            HumanMessage(content=f"""
Context:
{context}

Question:
{user_input}
""")
        )

        with st.chat_message("assistant"):
            with st.spinner("Thinking... 🤖"):
                response = st.session_state.llm.invoke(messages)
                answer = response.content
                st.markdown(answer)

                # ✅ Show sources
                with st.expander("📚 Sources"):
                    for d in docs:
                        st.write(f"📄 {d.metadata.get('source', 'Unknown')}")

        save_message(st.session_state.chat_id, "assistant", answer)

else:
    st.info("Upload PDFs and create/select a chat to begin.")