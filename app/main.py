"""TraceDoc Engine local Streamlit UI."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from app.evidence.models import (
    ANSWER_MODE_EVIDENCE_ONLY,
    ANSWER_MODE_GRAPH_STRUCTURED,
    ANSWER_MODE_NO_EVIDENCE,
    ANSWER_MODE_STRUCTURED_EXTRACTIVE,
)
from app.pipeline import process_document
from app.qa import DocumentQAResult, ask_document
from app.storage import (
    clear_local_data,
    get_document_processing_counts,
    initialize_database,
    list_audit_events,
    list_documents,
    load_document_schema,
    load_knowledge_graph,
)

DB_PATH = str(PROJECT_ROOT / "data" / "tracedoc.db")
UPLOAD_DIR = str(PROJECT_ROOT / "data" / "uploads")
INDEX_DIR = str(PROJECT_ROOT / "data" / "index")
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

CAPABILITIES = (
    ("Evidence retrieval", "BM25 over line-anchored chunks with citation cards"),
    ("Section-aware reasoning", "Section titles and semantic tree text for list answers"),
    ("Dynamic schema discovery", "Categories and grammars inferred from headings"),
    ("Symbolic grammar extraction", "Ordinal and pattern-based entity lists"),
    ("Knowledge graph matching", "Relationship answers from document graph edges"),
    ("Audit traceability", "Append-only local log of process and query events"),
)

ANSWER_MODE_LABELS: dict[str, str] = {
    ANSWER_MODE_GRAPH_STRUCTURED: (
        "Answered using deterministic graph matching."
    ),
    ANSWER_MODE_STRUCTURED_EXTRACTIVE: (
        "Answered using section/tree extraction and symbolic grammar."
    ),
    ANSWER_MODE_EVIDENCE_ONLY: "Answered using evidence retrieval only.",
    ANSWER_MODE_NO_EVIDENCE: "No reliable evidence found.",
}

ARCHITECTURE_DEMO_QUESTIONS = (
    "what are different architectures mentioned?",
    "what are different design patterns mentioned?",
    "What does Enterprise search stack use?",
    "What does Classic QA pipeline contain?",
)

GENERAL_DEMO_QUESTIONS = (
    "What is HPC6 memory policy?",
    "Where is CPU binding mentioned?",
    "What is REQ-001?",
    "List all storage rules",
)

DEMO_WARNING = (
    "TraceDoc does not generate free-form AI answers. It returns deterministic "
    "answers from extracted evidence, symbolic rules, and graph matches."
)

ARCHITECTURE_IMAGES_DIR = PROJECT_ROOT / "docs" / "images"
ARCHITECTURE_DIAGRAMS: tuple[tuple[str, str], ...] = (
    ("architecture-overview.png", "System overview (v0.1.0)"),
    ("architecture-document-pipeline.png", "Document processing pipeline (offline)"),
    ("architecture-qa-flow.png", "Question answering & answer modes (online)"),
    ("architecture-storage-modules.png", "SQLite persistence & app/ modules"),
)
ARCHITECTURE_DOC_URL = (
    "https://github.com/Satyam-Captain/TraceDoc-Engine/blob/master/docs/architecture.md"
)
ARCHITECTURE_DRAWIO_URL = (
    "https://github.com/Satyam-Captain/TraceDoc-Engine/blob/master/docs/architecture.drawio"
)

STACK_PRESETS: dict[str, dict[str, str]] = {
    "v1 — Classic": {
        "TRACEDOC_EXTRACTOR": "v1",
        "TRACEDOC_RETRIEVAL": "sqlite",
        "TRACEDOC_EXTRACTION": "grammar",
    },
    "v2 — Full stack": {
        "TRACEDOC_EXTRACTOR": "v2",
        "TRACEDOC_RETRIEVAL": "hybrid",
        "TRACEDOC_EXTRACTION": "both",
    },
}


def _preset_from_environment() -> str:
    """Map current env vars to a sidebar preset label."""
    extractor = os.environ.get("TRACEDOC_EXTRACTOR", "v1").lower()
    retrieval = os.environ.get("TRACEDOC_RETRIEVAL", "sqlite").lower()
    extraction = os.environ.get("TRACEDOC_EXTRACTION", "grammar").lower()
    for label, flags in STACK_PRESETS.items():
        if (
            flags["TRACEDOC_EXTRACTOR"] == extractor
            and flags["TRACEDOC_RETRIEVAL"] == retrieval
            and flags["TRACEDOC_EXTRACTION"] == extraction
        ):
            return label
    return "v2 — Full stack"


def apply_stack_preset(preset_label: str) -> dict[str, str]:
    """Apply a stack preset to os.environ for this Streamlit process."""
    flags = STACK_PRESETS[preset_label]
    for key, value in flags.items():
        os.environ[key] = value
    return dict(flags)


def _render_engine_stack_sidebar() -> dict[str, str]:
    """Sidebar toggle for v1 vs v2 without a second Streamlit port."""
    st.sidebar.subheader("Engine stack")
    preset_labels = list(STACK_PRESETS.keys())
    default_index = preset_labels.index(_preset_from_environment())
    preset = st.sidebar.radio(
        "Version",
        options=preset_labels,
        index=default_index,
        key="engine_stack_preset",
        help=(
            "v1: pypdf + SQLite BM25 + grammar only. "
            "v2: Docling PDF + hybrid Whoosh/SQLite + grammar + EntityRuler debug."
        ),
    )
    active = apply_stack_preset(preset)

    st.sidebar.markdown("**Active flags**")
    st.sidebar.code(
        "\n".join(f"{key}={value}" for key, value in active.items()),
        language="bash",
    )
    if preset.startswith("v2"):
        st.sidebar.caption(
            "v2 uses Docling for PDFs (heavy). Large PDFs may need v1 or more RAM."
        )
    st.sidebar.caption(
        "Switching stack does not re-index existing documents. "
        "Clear data or re-process after changing version."
    )
    return active


@dataclass(frozen=True)
class DocumentIndexMetadata:
    """Schema and graph summary for one indexed document."""

    schema_categories: tuple[str, ...]
    graph_node_count: int
    graph_edge_count: int


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


def load_document_index_metadata(
    db_path: str, document_id: int
) -> DocumentIndexMetadata:
    """Load schema category names and knowledge-graph counts for the UI."""
    schema = load_document_schema(db_path, document_id)
    categories: list[str] = []
    if schema is not None:
        for category in schema.categories:
            label = category.name.strip() or category.normalized_name
            if label and label not in categories:
                categories.append(label)

    graph = load_knowledge_graph(db_path, document_id)
    node_count = len(graph.nodes) if graph is not None else 0
    edge_count = len(graph.edges) if graph is not None else 0
    return DocumentIndexMetadata(
        schema_categories=tuple(categories),
        graph_node_count=node_count,
        graph_edge_count=edge_count,
    )


def suggested_demo_questions(
    file_name: str, metadata: DocumentIndexMetadata
) -> tuple[str, ...]:
    """Return demo question suggestions suited to the selected document."""
    lowered_name = file_name.lower()
    category_blob = " ".join(metadata.schema_categories).lower()
    architecture_signals = (
        "architect",
        "design pattern",
        "enterprise search",
        "qa pipeline",
        "knowledge graph",
        "symbolic",
    )
    if metadata.graph_edge_count > 0 and any(
        signal in lowered_name or signal in category_blob
        for signal in architecture_signals
    ):
        return ARCHITECTURE_DEMO_QUESTIONS
    if any(signal in lowered_name for signal in ("architecture", "symbolic")):
        return ARCHITECTURE_DEMO_QUESTIONS
    return GENERAL_DEMO_QUESTIONS


def _document_options(db_path: str) -> list[tuple[str, int, str]]:
    documents = list_documents(db_path)
    return [(f"{doc.id} - {doc.file_name}", doc.id, doc.file_name) for doc in documents]


def _render_header() -> None:
    st.title("TraceDoc Engine")
    st.subheader("Deterministic Symbolic Document Intelligence")
    st.caption("No LLM | No AI | No Embeddings | Local Only")
    st.info(DEMO_WARNING)


def _render_capability_panel() -> None:
    st.markdown("#### Capabilities")
    columns = st.columns(3)
    for index, (title, detail) in enumerate(CAPABILITIES):
        with columns[index % 3]:
            st.markdown(f"**{title}**")
            st.caption(detail)


def _render_processing_summary(
    *,
    document_id: int,
    file_name: str,
    section_count: int,
    chunk_count: int,
    indexed_term_count: int,
    duplicate: bool,
    metadata: DocumentIndexMetadata,
) -> None:
    st.markdown("#### Processing summary")
    metric_cols = st.columns(4)
    metric_cols[0].metric("Document ID", document_id)
    metric_cols[1].metric("Sections", section_count)
    metric_cols[2].metric("Chunks", chunk_count)
    metric_cols[3].metric("Indexed terms", indexed_term_count)

    detail_cols = st.columns(2)
    with detail_cols[0]:
        st.markdown(f"**File:** `{file_name}`")
        st.markdown(f"**Duplicate ingest:** `{duplicate}`")
        if metadata.schema_categories:
            st.markdown("**Schema categories:**")
            for category in metadata.schema_categories:
                st.markdown(f"- {category}")
        else:
            st.markdown("**Schema categories:** _none discovered yet_")
    with detail_cols[1]:
        if metadata.graph_node_count or metadata.graph_edge_count:
            st.markdown(
                f"**Knowledge graph:** {metadata.graph_node_count} nodes, "
                f"{metadata.graph_edge_count} edges"
            )
        else:
            st.markdown("**Knowledge graph:** _not available for this document_")


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
    _render_clear_data_sidebar(db_path)


def _render_clear_data_sidebar(db_path: str) -> None:
    st.sidebar.divider()
    st.sidebar.subheader("Data management")
    st.sidebar.caption(
        "Remove all indexed documents, questions history, audit log, and uploads "
        "so you can start fresh."
    )

    confirm = st.sidebar.checkbox(
        "I want to delete all local TraceDoc data",
        key="confirm_clear_data",
    )
    if st.sidebar.button(
        "Clear all local data",
        type="secondary",
        disabled=not confirm,
        help="Deletes the database and uploaded files for this app.",
    ):
        report = clear_local_data(
            db_path,
            upload_dir=UPLOAD_DIR,
            index_dir=INDEX_DIR,
        )
        if report.get("error"):
            st.sidebar.error(
                "Could not clear all data. Close other apps using the database "
                f"and try again.\n\n{report['error']}"
            )
            return

        initialize_database(db_path)
        st.sidebar.success(
            "Local data cleared. Upload and process documents again."
        )
        st.session_state.pop("confirm_clear_data", None)
        st.rerun()


def _render_upload_section(db_path: str) -> None:
    st.header("Upload & process")
    st.caption(
        "Ingest PDF, DOCX, or TXT into the local index with schema, tree, and graph."
    )
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

            metadata = load_document_index_metadata(db_path, result.document_id)
            st.success("Document processed successfully.")
            _render_processing_summary(
                document_id=result.document_id,
                file_name=result.file_name,
                section_count=result.section_count,
                chunk_count=result.chunk_count,
                indexed_term_count=result.indexed_term_count,
                duplicate=result.duplicate,
                metadata=metadata,
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


def _render_answer_mode_badge(answer: DocumentQAResult) -> None:
    mode_label = ANSWER_MODE_LABELS.get(
        answer.answer_mode, f"Answer mode: {answer.answer_mode}"
    )
    st.markdown(f"**Answer mode:** `{answer.answer_mode}`")
    st.caption(mode_label)


def _render_answer_block(answer: DocumentQAResult) -> None:
    st.markdown("### A. Answer")
    _render_answer_mode_badge(answer)

    if answer.answer_mode == ANSWER_MODE_NO_EVIDENCE:
        st.warning(answer.no_evidence_message or "No evidence found.")
        if answer.explanation:
            st.caption(answer.explanation)
        return

    if answer.answer_mode == ANSWER_MODE_GRAPH_STRUCTURED and answer.structured_answer:
        st.markdown("**Graph-based answer**")
        st.markdown(answer.structured_answer)
    elif (
        answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
        and answer.structured_answer
    ):
        st.markdown("**Structured extractive answer**")
        st.markdown(answer.structured_answer)
        if answer.section_retrieval_used and answer.retrieved_section_title:
            st.caption(
                "Section-level retrieval: "
                f"**{answer.retrieved_section_title}**"
            )
    elif answer.answer_mode == ANSWER_MODE_EVIDENCE_ONLY:
        st.markdown("**Evidence-only answer**")
        st.markdown(
            "No structured list was composed; review supporting evidence cards below."
        )
    elif answer.structured_answer:
        st.markdown(answer.structured_answer)

    if answer.explanation and answer.answer_mode != ANSWER_MODE_NO_EVIDENCE:
        st.caption(answer.explanation)


def _render_supporting_evidence(answer: DocumentQAResult) -> None:
    st.markdown("### B. Supporting evidence")
    if not answer.cards:
        st.info("No evidence cards were returned for this question.")
        return

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
            display_snippet = card.snippet.replace("[[", "**").replace("]]", "**")
            st.markdown(display_snippet)


def _render_debug_trace(answer: DocumentQAResult) -> None:
    st.markdown("### C. Debug trace")
    if not answer.debug_trace:
        st.caption("No debug trace recorded for this query.")
        return
    with st.expander("Show debug trace", expanded=False):
        for line in answer.debug_trace:
            st.code(line)


def _render_query_metadata(answer: DocumentQAResult) -> None:
    meta_cols = st.columns(2)
    with meta_cols[0]:
        if answer.query_intent is not None:
            st.markdown("**Detected intent**")
            st.markdown(f"- **Type:** `{answer.query_intent.intent_type}`")
            st.markdown(f"- **Explanation:** {answer.query_intent.explanation}")
            if answer.query_intent.entities:
                st.markdown(
                    f"- **Entities:** {', '.join(answer.query_intent.entities)}"
                )
    with meta_cols[1]:
        st.markdown("**Retrieval**")
        st.markdown(f"- **Strategy:** `{answer.retrieval_strategy}`")
        if answer.retrieved_section_title:
            st.markdown(f"- **Section:** {answer.retrieved_section_title}")


def _render_question_suggestions(
    suggestions: tuple[str, ...], *, key_prefix: str
) -> None:
    st.markdown("**Suggested demo questions**")
    suggestion_cols = st.columns(2)
    for index, suggestion in enumerate(suggestions):
        column = suggestion_cols[index % 2]
        if column.button(
            suggestion,
            key=f"{key_prefix}_suggest_{index}",
            use_container_width=True,
        ):
            st.session_state["pending_question"] = suggestion
            st.rerun()


def _render_question_section(db_path: str) -> None:
    st.header("Ask a question")
    options = _document_options(db_path)

    if not options:
        st.info("Upload and process a document first to enable questions.")
        return

    labels = [label for label, _, _ in options]
    id_by_label = {label: doc_id for label, doc_id, _ in options}
    name_by_label = {label: file_name for label, _, file_name in options}

    selected_label = st.selectbox(
        "Select indexed document",
        labels,
        help="Choose a processed document from the local index.",
    )
    document_id = id_by_label[selected_label]
    file_name = name_by_label[selected_label]
    metadata = load_document_index_metadata(db_path, document_id)
    section_count, chunk_count, indexed_term_count = get_document_processing_counts(
        db_path, document_id
    )

    with st.expander("Document index details", expanded=False):
        _render_processing_summary(
            document_id=document_id,
            file_name=file_name,
            section_count=section_count,
            chunk_count=chunk_count,
            indexed_term_count=indexed_term_count,
            duplicate=False,
            metadata=metadata,
        )

    suggestions = suggested_demo_questions(file_name, metadata)
    _render_question_suggestions(suggestions, key_prefix=f"doc_{document_id}")

    if "pending_question" in st.session_state:
        st.session_state["question_input"] = st.session_state.pop("pending_question")

    question = st.text_input(
        "Ask a question about the selected document",
        placeholder="Example: what are different architectures mentioned?",
        key="question_input",
    )

    if st.button("Ask question", type="primary"):
        if not question.strip():
            st.warning("Enter a question before searching for evidence.")
            return

        try:
            with st.spinner("Running deterministic QA pipeline..."):
                answer = ask_document(question, document_id, db_path=db_path)

            st.divider()
            _render_query_metadata(answer)
            st.divider()
            _render_answer_block(answer)
            st.divider()
            _render_supporting_evidence(answer)
            st.divider()
            _render_debug_trace(answer)
        except ValueError as error:
            st.error(str(error))
        except Exception as error:
            st.error(f"Search failed: {error}")


def _architecture_image_path(filename: str) -> Path | None:
    path = ARCHITECTURE_IMAGES_DIR / filename
    return path if path.is_file() else None


def _render_architecture_section() -> None:
    st.header("Architecture")
    st.caption(
        "Deterministic symbolic document intelligence — no LLM, embeddings, or external APIs."
    )
    st.markdown(
        f"- Full narrative: [architecture.md]({ARCHITECTURE_DOC_URL})\n"
        f"- Editable diagram source: [architecture.drawio]({ARCHITECTURE_DRAWIO_URL})"
    )

    missing = [
        filename
        for filename, _ in ARCHITECTURE_DIAGRAMS
        if _architecture_image_path(filename) is None
    ]
    if missing:
        st.warning(
            "Architecture images not found in `docs/images/`: "
            + ", ".join(missing)
        )

    for filename, caption in ARCHITECTURE_DIAGRAMS:
        image_path = _architecture_image_path(filename)
        if image_path is None:
            continue
        st.markdown(f"#### {caption}")
        st.image(str(image_path), use_container_width=True)

    st.divider()
    st.markdown(
        "**Release:** v0.1.0 · Evidence → section/tree → schema/grammar → "
        "knowledge graph → BM25 fallback"
    )


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
    _render_header()
    _render_capability_panel()
    st.divider()

    view = st.sidebar.radio(
        "View",
        options=("Document QA demo", "Architecture"),
        index=0,
        help="Switch between the live demo and architecture diagrams.",
    )

    if view == "Architecture":
        _render_architecture_section()
        return

    _render_engine_stack_sidebar()
    initialize_database(DB_PATH)
    _render_sidebar(DB_PATH)
    _render_upload_section(DB_PATH)
    st.divider()
    _render_question_section(DB_PATH)
    st.divider()
    _render_audit_section(DB_PATH)


if __name__ == "__main__":
    main()
