"""
Voice RAG Agent — Fully Local Edition

A fully local, $0, offline variant of rag_voice.py:
  - LLM       : LM Studio (OpenAI-compatible local server, default :1234)
                  -> swap to Ollama by changing the base_url (see setup_agents)
  - Embeddings: FastEmbed (already local in the original)
  - Vector DB : Qdrant embedded local mode (./qdrant_local, no cloud, no Docker)
  - TTS       : Kokoro (local neural TTS) -> Piper is a lighter alternative

No API keys. No outbound network calls once models are downloaded locally.

Run:
  1. LM Studio: load a model, then Developer -> Local Server -> Start (port 1234)
  2. System dep for Kokoro:  apt-get install espeak-ng   (mac: brew install espeak-ng)
  3. pip install -r requirements-local.txt
  4. streamlit run rag_voice_local.py
"""

from typing import List, Dict, Tuple
import os
import tempfile
from datetime import datetime
import uuid
import asyncio

import streamlit as st
import numpy as np
import soundfile as sf
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from fastembed import TextEmbedding
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, set_tracing_disabled

load_dotenv()

# Constants
COLLECTION_NAME = "voice-rag-agent"
QDRANT_LOCAL_PATH = "./qdrant_local"

# LM Studio defaults (OpenAI-compatible local server).
# To use Ollama instead, set base_url to "http://localhost:11434/v1".
DEFAULT_LLM_BASE_URL = "http://localhost:1234/v1"
DEFAULT_MODEL_NAME = "local-model"  # any string; LM Studio uses the loaded model

# Kokoro voices (lang_code "a" = American English; "b" = British).
KOKORO_VOICES = [
    "af_heart", "af_bella", "af_nicole", "af_sarah",
    "am_michael", "am_fenrir", "am_puck",
    "bf_emma", "bm_george",
]


def init_session_state() -> None:
    """Initialize Streamlit session state with default values."""
    defaults = {
        "initialized": False,
        "llm_base_url": DEFAULT_LLM_BASE_URL,
        "model_name": DEFAULT_MODEL_NAME,
        "setup_complete": False,
        "client": None,
        "embedding_model": None,
        "processor_agent": None,
        "kokoro_pipeline": None,
        "selected_voice": "af_heart",
        "processed_documents": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def setup_sidebar() -> None:
    """Configure sidebar with local LLM settings and voice options."""
    with st.sidebar:
        st.title("🔧 Local Configuration")
        st.markdown("---")
        st.markdown("### 🧠 Local LLM (LM Studio / Ollama)")
        st.session_state.llm_base_url = st.text_input(
            "LLM Base URL",
            value=st.session_state.llm_base_url,
            help="LM Studio: http://localhost:1234/v1 · Ollama: http://localhost:11434/v1",
        )
        st.session_state.model_name = st.text_input(
            "Model name",
            value=st.session_state.model_name,
            help="LM Studio uses the loaded model regardless. For Ollama use e.g. 'llama3.1'.",
        )

        st.markdown("---")
        st.markdown("### 🎤 Voice (Kokoro, local)")
        st.session_state.selected_voice = st.selectbox(
            "Select Voice",
            options=KOKORO_VOICES,
            index=KOKORO_VOICES.index(st.session_state.selected_voice),
            help="Local neural TTS voice",
        )


def setup_qdrant() -> Tuple[QdrantClient, TextEmbedding]:
    """Initialize a LOCAL embedded Qdrant client and the embedding model."""
    # Local embedded mode: persists to a folder, no server / Docker / cloud needed.
    client = QdrantClient(path=QDRANT_LOCAL_PATH)

    embedding_model = TextEmbedding()
    embedding_dim = len(list(embedding_model.embed(["test"]))[0])

    try:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE),
        )
    except Exception as e:
        if "already exists" not in str(e):
            raise e

    return client, embedding_model


def process_pdf(file) -> List:
    """Process PDF file and split into chunks with metadata."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(file.getvalue())
            loader = PyPDFLoader(tmp_file.name)
            documents = loader.load()

            for doc in documents:
                doc.metadata.update(
                    {
                        "source_type": "pdf",
                        "file_name": file.name,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000, chunk_overlap=200
            )
            return text_splitter.split_documents(documents)
    except Exception as e:
        st.error(f"📄 PDF processing error: {str(e)}")
        return []


def store_embeddings(
    client: QdrantClient,
    embedding_model: TextEmbedding,
    documents: List,
    collection_name: str,
) -> None:
    """Store document embeddings in Qdrant."""
    for doc in documents:
        embedding = list(embedding_model.embed([doc.page_content]))[0]
        client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding.tolist(),
                    payload={"content": doc.page_content, **doc.metadata},
                )
            ],
        )


def setup_agent(base_url: str, model_name: str) -> Agent:
    """Initialize the processor agent pointed at a local OpenAI-compatible server."""
    # Disable tracing so the agents SDK does not try to call OpenAI in the background.
    set_tracing_disabled(True)

    local_client = AsyncOpenAI(base_url=base_url, api_key="local")
    model = OpenAIChatCompletionsModel(model=model_name, openai_client=local_client)

    processor_agent = Agent(
        name="Documentation Processor",
        instructions="""You are a helpful documentation assistant. Your task is to:
        1. Analyze the provided documentation content
        2. Answer the user's question clearly and concisely
        3. Include relevant examples when available
        4. Cite the source files when referencing specific content
        5. Keep responses natural and conversational
        6. Format your response so it is easy to speak out loud""",
        model=model,
    )
    return processor_agent


def synthesize_speech(pipeline, text: str, voice: str) -> str:
    """Local TTS via Kokoro. Returns a path to a WAV file."""
    chunks = [audio for _, _, audio in pipeline(text, voice=voice)]
    audio = np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)

    audio_path = os.path.join(tempfile.gettempdir(), f"response_{uuid.uuid4()}.wav")
    sf.write(audio_path, audio, 24000)  # Kokoro outputs 24 kHz
    return audio_path


async def process_query(
    query: str,
    client: QdrantClient,
    embedding_model: TextEmbedding,
    collection_name: str,
    voice: str,
) -> Dict:
    """Process user query and generate a local voice response."""
    try:
        st.info("🔄 Step 1: Embedding query and searching documents...")
        query_embedding = list(embedding_model.embed([query]))[0]

        search_response = client.query_points(
            collection_name=collection_name,
            query=query_embedding.tolist(),
            limit=3,
            with_payload=True,
        )
        search_results = (
            search_response.points if hasattr(search_response, "points") else []
        )
        st.write(f"Found {len(search_results)} relevant chunks")

        if not search_results:
            raise Exception("No relevant documents found in the vector database")

        st.info("🔄 Step 2: Building context...")
        context = "Based on the following documentation:\n\n"
        for i, result in enumerate(search_results, 1):
            payload = result.payload
            if not payload:
                continue
            content = payload.get("content", "")
            source = payload.get("file_name", "Unknown Source")
            context += f"From {source}:\n{content}\n\n"
            st.write(f"Chunk {i} from: {source}")

        context += f"\nUser Question: {query}\n\n"
        context += "Provide a clear, concise answer that can be easily spoken out loud."

        st.info("🔄 Step 3: Generating answer (local LLM)...")
        processor_result = await Runner.run(st.session_state.processor_agent, context)
        text_response = processor_result.final_output

        st.info("🔄 Step 4: Synthesizing speech (local Kokoro)...")
        audio_path = synthesize_speech(
            st.session_state.kokoro_pipeline, text_response, voice
        )

        st.success("✅ Query processing complete!")
        return {
            "status": "success",
            "text_response": text_response,
            "audio_path": audio_path,
            "sources": [
                r.payload.get("file_name", "Unknown Source")
                for r in search_results
                if r.payload
            ],
        }

    except Exception as e:
        st.error(f"❌ Error during query processing: {str(e)}")
        return {"status": "error", "error": str(e), "query": query}


def main() -> None:
    """Main application function."""
    st.set_page_config(page_title="Voice RAG Agent (Local)", page_icon="🎙️", layout="wide")

    init_session_state()
    setup_sidebar()

    st.title("🎙️ Voice RAG Agent — Local Edition")
    st.info(
        "Fully local, offline voice RAG. Load a model in LM Studio (or run Ollama), "
        "upload a PDF, and ask questions to get text + locally-synthesized voice answers."
    )

    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

    if uploaded_file:
        file_name = uploaded_file.name
        if file_name not in st.session_state.processed_documents:
            with st.spinner("Processing PDF..."):
                try:
                    if not st.session_state.client:
                        client, embedding_model = setup_qdrant()
                        st.session_state.client = client
                        st.session_state.embedding_model = embedding_model

                    # Lazy-init the local LLM agent and Kokoro TTS pipeline once.
                    if not st.session_state.processor_agent:
                        st.session_state.processor_agent = setup_agent(
                            st.session_state.llm_base_url, st.session_state.model_name
                        )
                    if not st.session_state.kokoro_pipeline:
                        from kokoro import KPipeline  # imported here so app starts fast

                        st.session_state.kokoro_pipeline = KPipeline(lang_code="a")

                    documents = process_pdf(uploaded_file)
                    if documents:
                        store_embeddings(
                            st.session_state.client,
                            st.session_state.embedding_model,
                            documents,
                            COLLECTION_NAME,
                        )
                        st.session_state.processed_documents.append(file_name)
                        st.success(f"✅ Added PDF: {file_name}")
                        st.session_state.setup_complete = True
                except Exception as e:
                    st.error(f"Error processing document: {str(e)}")

    if st.session_state.processed_documents:
        st.sidebar.header("📚 Processed Documents")
        for doc in st.session_state.processed_documents:
            st.sidebar.text(f"📄 {doc}")

    query = st.text_input(
        "What would you like to know about the documentation?",
        placeholder="e.g., How do I authenticate API requests?",
        disabled=not st.session_state.setup_complete,
    )

    if query and st.session_state.setup_complete:
        with st.status("Processing your query...", expanded=True) as status:
            try:
                result = asyncio.run(
                    process_query(
                        query,
                        st.session_state.client,
                        st.session_state.embedding_model,
                        COLLECTION_NAME,
                        st.session_state.selected_voice,
                    )
                )

                if result["status"] == "success":
                    status.update(label="✅ Query processed!", state="complete")

                    st.markdown("### Response:")
                    st.write(result["text_response"])

                    if "audio_path" in result:
                        st.markdown(
                            f"### 🔊 Audio Response (Voice: {st.session_state.selected_voice})"
                        )
                        st.audio(result["audio_path"], format="audio/wav", start_time=0)

                        with open(result["audio_path"], "rb") as audio_file:
                            st.download_button(
                                label="📥 Download Audio Response",
                                data=audio_file.read(),
                                file_name=f"voice_response_{st.session_state.selected_voice}.wav",
                                mime="audio/wav",
                            )

                    st.markdown("### Sources:")
                    for source in result["sources"]:
                        st.markdown(f"- {source}")
                else:
                    status.update(label="❌ Error processing query", state="error")
                    st.error(f"Error: {result.get('error', 'Unknown error occurred')}")

            except Exception as e:
                status.update(label="❌ Error processing query", state="error")
                st.error(f"Error processing query: {str(e)}")

    elif not st.session_state.setup_complete:
        st.info("👈 Start your local LLM server, then upload a PDF to begin!")


if __name__ == "__main__":
    main()
