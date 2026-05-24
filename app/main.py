"""TraceDoc Engine local Streamlit UI."""

from __future__ import annotations

import json
import re
from pathlib import Path

import streamlit as st

from app.pipeline import process_document
from app.qa import ask_document
from app.storage import initialize_database, list_audit_events, list_documents

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = str(PROJECT_ROOT / "data" / "tracedoc.db")
UPLOAD_DIR = str(PROJECT_ROOT / "data" / "uploads")
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def save_uploaded_file(uploaded_file, upload_dir: str = UPLOAD_DIR) -> str:
    """
    Save an uploaded file under upload_dir using a safe filename.

    Returns the absolute path to the saved file.
    """
    upload_path = Path(upload_dir).resolve()
    upload_path.mkdir(parents=True, exist_ok=True)

    original_name = uploaded_file.name
    if (
        not original_name
        or ".." in original_name
        or "/" in original_name
        or "\\" in original_name
    ):
        raise ValueError("Unsafe upload filename")

    safe_name = re.sub(
        r'[<>:"|?*\\/\x00-\x1f]', "_", Path(original_name).name
    ).strip()
    if not safe_name or safe_name in {".", ".."}:
        safe_name = "upload.bin"

    destination = (upload_path / safe_name).resolve()
    if destination.parent != upload_path:
        raise ValueError("Unsafe upload filename")

    data = uploaded_file.getvalue()
    destination.write_bytes(data)
    return str(destination)


def _document_options(db_path: str) -> list[tuple[str, int]]:
    documents = list_documents(db_path)
    return [(f"{doc.id} - {doc.file_name}", doc.id) for doc in documents]


def _render_header() -> None:
    st.title("TraceDoc Engine")
    st.subheader("Deterministic Evidence-Based Document QA")
    st.caption("No LLM | No AI | Local Only")


def _render_sidebar(db_path: str) -> None:
    st.sidebar.header("TraceDoc Engine")
    st.sidebar.markdown(
        """
**Hard constraints**
- No LLM
- No AI / ML models
- No embeddings
- No vector search
- No external API
- Local-only execution
        """
    )
    st.sidebar.markdown(f"**Database path:** `{db_path}`")

    try:
        document_count = len(list_documents(db_path))
    except Exception:
        document_count = 0
    st.sidebar.metric("Indexed documents", document_count)


def _render_upload_section(db_path: str) -> None:
    st.header("Upload document")
    uploaded = st.file_uploader(
        "Upload a document",
        type=["pdf", "docx", "txt"],
        help="Supported formats: PDF, DOCX, TXT",
    )

    if uploaded is None:
        return

    extension = Path(uploaded.name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        st.error(f"Unsupported file type: {extension}")
        return

    if st.button("Process document", type="primary"):
        try:
            saved_path = save_uploaded_file(uploaded)
            with st.spinner("Processing document..."):
                result = process_document(saved_path, db_path=db_path)

            st.success("Document processed successfully.")
            st.markdown(
                f"""
- **Document ID:** {result.document_id}
- **File name:** {result.file_name}
- **Sections:** {result.section_count}
- **Chunks:** {result.chunk_count}
- **Indexed terms:** {result.indexed_term_count}
- **Duplicate:** {result.duplicate}
                """
            )
            if result.warnings:
                st.warning("Processing warnings:")
                for warning in result.warnings:
                    st.write(f"- {warning}")
        except FileNotFoundError as error:
            st.error(f"File not found: {error}")
        except ValueError as error:
            st.error(f"Processing failed: {error}")
        except Exception as error:
            st.error(f"Unexpected processing error: {error}")


def _render_question_section(db_path: str) -> None:
    st.header("Ask a question")
    options = _document_options(db_path)

    if not options:
        st.info("Upload and process a document first to enable questions.")
        return

    labels = [label for label, _ in options]
    selected_label = st.selectbox(
        "Select indexed document",
        labels,
        help="Choose a processed document from the local index.",
    )
    document_id = dict(options)[selected_label]

    question = st.text_input(
        "Ask a question about the selected document",
        placeholder="Example: What are the HPC6 memory requirements?",
    )

    if st.button("Search evidence", type="primary"):
        if not question.strip():
            st.warning("Enter a question before searching for evidence.")
            return

        try:
            with st.spinner("Searching evidence..."):
                answer = ask_document(question, document_id, db_path=db_path)

            if answer.query_intent is not None:
                st.markdown("**Detected intent**")
                st.markdown(f"- **Intent type:** `{answer.query_intent.intent_type}`")
                st.markdown(f"- **Explanation:** {answer.query_intent.explanation}")
                if answer.query_intent.entities:
                    st.markdown(
                        f"- **Entities:** {', '.join(answer.query_intent.entities)}"
                    )

            if answer.answer_mode == "NO_EVIDENCE":
                st.warning(answer.no_evidence_message or "No evidence found.")
                st.caption(answer.explanation)
                return

            st.success("Evidence cards")
            st.caption(answer.explanation)

            for index, card in enumerate(answer.cards, start=1):
                with st.expander(
                    f"Evidence {index} — {card.confidence} — {card.citation}",
                    expanded=index == 1,
                ):
                    st.markdown(f"**Confidence:** {card.confidence}")
                    st.markdown(f"**Citation:** {card.citation}")
                    st.markdown(f"**Score:** {card.score:.4f}")
                    st.markdown(f"**Why matched:** {card.why_matched}")
                    st.markdown("**Snippet:**")
                    display_snippet = card.snippet.replace("[[", "**").replace(
                        "]]", "**"
                    )
                    st.markdown(display_snippet)
        except ValueError as error:
            st.error(str(error))
        except Exception as error:
            st.error(f"Search failed: {error}")


def _render_audit_section(db_path: str) -> None:
    st.header("Audit / Traceability")
    st.caption("Append-only local audit log for document processing and questions.")

    try:
        events = list_audit_events(db_path, limit=100)
    except Exception as error:
        st.error(f"Unable to load audit events: {error}")
        return

    if not events:
        st.info("No audit events recorded yet.")
        return

    for event in reversed(events):
        with st.expander(
            f"{event.created_at or 'unknown time'} — {event.event_type}",
            expanded=False,
        ):
            st.markdown(f"**Event type:** {event.event_type}")
            st.markdown(f"**Timestamp:** {event.created_at}")
            if event.document_id is not None:
                st.markdown(f"**Document ID:** {event.document_id}")
            st.markdown("**Details:**")
            st.code(json.dumps(event.details, indent=2, sort_keys=True), language="json")


def main() -> None:
    """Render the TraceDoc Engine Streamlit application."""
    st.set_page_config(
        page_title="TraceDoc Engine",
        page_icon="📄",
        layout="wide",
    )
    initialize_database(DB_PATH)
    _render_header()
    _render_sidebar(DB_PATH)
    _render_upload_section(DB_PATH)
    st.divider()
    _render_question_section(DB_PATH)
    st.divider()
    _render_audit_section(DB_PATH)


if __name__ == "__main__":
    main()
