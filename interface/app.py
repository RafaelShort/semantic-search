"""
Interface web do Motor de Busca Semântico.
Execute com: streamlit run interface/app.py
"""

import time

import requests
import streamlit as st

# Configuração da página
st.set_page_config(
    page_title="Motor de Busca Semântico",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = "http://localhost:8000/api/v1"

# CSS customizado
st.markdown(
    """
<style>
    .stApp { background-color: #0f1117; }

    .main-header {
        text-align: center;
        padding: 1.5rem 0 0.5rem 0;
    }
    .main-header h1 {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #4f6ef7, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
    }
    .main-header p {
        color: #8892b0;
        font-size: 1.05rem;
    }

    .result-card {
        background: linear-gradient(135deg, #1e2130 0%, #252840 100%);
        border: 1px solid #2d3250;
        border-radius: 14px;
        padding: 20px 24px;
        margin: 14px 0;
        transition: all 0.2s ease;
    }
    .result-card:hover {
        border-color: #4f6ef7;
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(79, 110, 247, 0.15);
    }

    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }
    .badge-hybrid   { background: #1a3a5c; color: #4fc3f7; }
    .badge-semantic { background: #1a3a2a; color: #81c784; }
    .badge-keyword  { background: #3a1a4a; color: #ce93d8; }

    .score-bar-bg {
        background: #1a1d2e;
        border-radius: 4px;
        height: 5px;
        margin: 10px 0 14px 0;
        overflow: hidden;
    }
    .score-bar-fill {
        height: 100%;
        border-radius: 4px;
        background: linear-gradient(90deg, #4f6ef7, #a78bfa);
    }

    /* ── Status boxes ── */
    .status-box {
        border-radius: 10px;
        padding: 10px 14px;
        margin-bottom: 14px;
        font-size: 0.9rem;
    }
    .status-ok   { background: #0d2b0d; border: 1px solid #2d5a2d; }
    .status-warn { background: #2b2a0d; border: 1px solid #5a552d; }  /* ← novo */
    .status-err  { background: #2b0d0d; border: 1px solid #5a2d2d; }

    .example-card {
        background: #1e2130;
        border: 1px solid #2d3250;
        border-radius: 10px;
        padding: 14px 20px;
        text-align: center;
        transition: border-color 0.2s;
    }
    .example-card:hover { border-color: #4f6ef7; }

    div[data-testid="stTextInput"] > label { display: none; }
</style>
""",
    unsafe_allow_html=True,
)


# Funções de API

def api_health() -> dict | None:
    try:
        r = requests.get(f"{API_BASE}/health", timeout=3)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def api_stats() -> dict | None:
    try:
        r = requests.get(f"{API_BASE}/stats", timeout=3)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def api_search(
    query: str,
    mode: str,
    top_k: int,
    semantic_weight: float,
    keyword_weight: float,
    rerank: bool,
    deduplicate: bool,
) -> dict | None:
    try:
        payload = {
            "query":            query,
            "mode":             mode,
            "top_k":            top_k,
            "semantic_weight":  semantic_weight,
            "keyword_weight":   keyword_weight,
            "rerank":           rerank,
            "deduplicate":      deduplicate,
        }
        r = requests.post(f"{API_BASE}/search", json=payload, timeout=30)
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        st.error(f"Erro ao conectar à API: {e}")
        return None


def api_ingest_url(url: str) -> dict | None:
    try:
        r = requests.post(
            f"{API_BASE}/ingest/url",
            json={"url": url},
            timeout=120,
        )
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def api_ingest_file(file_bytes: bytes, filename: str) -> dict | None:
    try:
        r = requests.post(
            f"{API_BASE}/ingest/file",
            files={"file": (filename, file_bytes)},
            timeout=120,
        )
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


# Header
st.markdown(
    """
<div class="main-header">
    <h1>🔍 Motor de Busca Semântico</h1>
    <p>Busca inteligente por <strong style="color:#a78bfa;">significado</strong>,
    não apenas palavras-chave</p>
</div>
""",
    unsafe_allow_html=True,
)

# Sidebar
with st.sidebar:
    st.markdown("## ⚙️ Painel de Controle")

    # Status da API
    health = api_health()

    if health is not None:                          
        mongo_icon = "✅" if health.get("mongodb")        else "❌"
        es_icon    = "✅" if health.get("elasticsearch")  else "❌"
        api_status = health.get("status", "degraded")

        if api_status == "healthy":
            box_class  = "status-ok"
            title      = "🟢 <strong>Sistemas Online</strong>"
        else:
            box_class  = "status-warn"
            title      = "🟡 <strong>API Online — serviços degradados</strong>"

        st.markdown(
            f"""
            <div class="status-box {box_class}">
                {title}<br>
                <span style="color:#8892b0; font-size:0.82rem;">
                    🍃 MongoDB {mongo_icon} &nbsp;|&nbsp; 🔍 ElasticSearch {es_icon}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:                                       
        st.markdown(
            """
            <div class="status-box status-err">
                🔴 <strong>API Offline</strong><br>
                <span style="color:#8892b0; font-size:0.82rem;">
                    Rode: uvicorn src.api.main:app --reload
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Estatísticas
    stats = api_stats()
    if stats:
        st.markdown("### 📊 Estatísticas")
        c1, c2 = st.columns(2)
        c1.metric("📄 Documentos", stats.get("total_documents", 0))
        c2.metric("✂️ Chunks",     stats.get("total_chunks", 0))

        indexed = stats.get("indexed_chunks", 0)
        total   = stats.get("total_chunks", 1)
        pct     = int((indexed / total) * 100) if total else 0
        st.metric("🔍 Indexados no ES", f"{indexed} ({pct}%)")

    st.divider()

    # Ingestão
    st.markdown("### 📥 Ingerir Documento")
    ingest_mode = st.radio(
        "Tipo de ingestão",
        ["🌐 URL", "📄 Arquivo"],
        label_visibility="collapsed",
    )

    if ingest_mode == "🌐 URL":
        url_input = st.text_input(
            "URL",
            placeholder="https://pt.wikipedia.org/wiki/...",
        )
        if st.button("⬇️ Ingerir URL", use_container_width=True, type="primary"):
            if url_input.strip():
                with st.spinner("Processando URL..."):
                    result = api_ingest_url(url_input.strip())
                if result and result.get("success"):
                    st.success(f"✅ {result['chunks_count']} chunks criados!")
                    st.rerun()
                else:
                    st.error("❌ Falha na ingestão. Verifique a URL.")
            else:
                st.warning("Digite uma URL válida.")

    else:
        uploaded = st.file_uploader(
            "Arquivo",
            type=["pdf", "txt", "docx"],
            label_visibility="collapsed",
        )
        if uploaded:
            if st.button("⬇️ Ingerir Arquivo", use_container_width=True, type="primary"):
                with st.spinner(f"Processando {uploaded.name}..."):
                    result = api_ingest_file(uploaded.read(), uploaded.name)
                if result and result.get("success"):
                    st.success(f"✅ {result['chunks_count']} chunks criados!")
                    st.rerun()
                else:
                    st.error("❌ Falha na ingestão.")


# Modo de busca
MODE_MAP = {
    "⚡ Híbrida":        "hybrid",
    "🧠 Semântica":      "semantic",
    "🔤 Palavras-chave": "keyword",
}

selected_label = st.radio(
    "Modo de busca",
    list(MODE_MAP.keys()),
    horizontal=True,
    help=(
        "**Híbrida**: combina semântica + BM25 (melhor resultado geral)\n\n"
        "**Semântica**: encontra por significado, mesmo sem palavras em comum\n\n"
        "**Palavras-chave**: busca exata com BM25"
    ),
)
mode = MODE_MAP[selected_label]

# Campo de busca
col_input, col_btn = st.columns([6, 1], vertical_alignment="bottom")

with col_input:
    query = st.text_input(
        "Busca",
        placeholder="Ex: como funciona aprendizado de máquina...",
        key="search_query",
        label_visibility="collapsed",
    )

with col_btn:
    search_btn = st.button("🔍 Buscar", use_container_width=True, type="primary")

# Opções avançadas
with st.expander("⚙️ Opções avançadas"):
    ac1, ac2, ac3, ac4 = st.columns(4)

    with ac1:
        top_k = st.slider("Nº de resultados", 1, 20, 5)

    with ac2:
        semantic_weight = st.slider(
            "Peso semântico",
            0.0, 1.0, 0.7, 0.05,
            disabled=(mode != "hybrid"),
        )

    with ac3:
        keyword_weight = st.slider(
            "Peso keyword",
            0.0, 1.0, 0.3, 0.05,
            disabled=(mode != "hybrid"),
        )

    with ac4:
        rerank      = st.checkbox("Reranking",  value=True)
        deduplicate = st.checkbox("Deduplicar", value=True)

st.divider()

# Execução da busca e resultados
if search_btn and query.strip():
    with st.spinner("🔍 Buscando..."):
        t0           = time.time()
        results_data = api_search(
            query=           query,
            mode=            mode,
            top_k=           top_k,
            semantic_weight= semantic_weight,
            keyword_weight=  keyword_weight,
            rerank=          rerank,
            deduplicate=     deduplicate,
        )
        elapsed_ms = (time.time() - t0) * 1000

    if results_data:
        results  = results_data.get("results", [])
        total    = results_data.get("total_results", 0)
        api_time = results_data.get("time_ms", elapsed_ms)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📄 Resultados",  total)
        m2.metric("⏱️ Tempo (API)", f"{api_time:.0f} ms")
        m3.metric("🔎 Modo",        selected_label)
        m4.metric("🔀 Reranking",   "✅ Ativo" if rerank else "❌ Inativo")

        st.markdown("---")

        if results:
            for i, res in enumerate(results):
                score       = res.get("score", 0.0)
                score_pct   = min(int(score * 100), 100)
                source      = res.get("source", "desconhecido")
                content     = res.get("content", "")
                search_type = res.get("search_type", mode)
                chunk_idx   = res.get("chunk_index", 0)

                badge_class = {
                    "hybrid":   "badge-hybrid",
                    "semantic": "badge-semantic",
                    "keyword":  "badge-keyword",
                }.get(search_type, "badge-hybrid")

                badge_label = {
                    "hybrid":   "Híbrida",
                    "semantic": "Semântica",
                    "keyword":  "Keyword",
                }.get(search_type, search_type)

                preview = content[:420] + ("..." if len(content) > 420 else "")

                st.markdown(
                    f"""
                    <div class="result-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <span style="color:#8892b0; font-size:0.82rem;">#{i + 1}</span>
                                <span style="color:#cdd6f4; font-weight:700;
                                             margin-left:8px;">📄 {source}</span>
                                <span style="color:#8892b0; font-size:0.78rem;
                                             margin-left:8px;">chunk #{chunk_idx}</span>
                            </div>
                            <div>
                                <span class="badge {badge_class}">{badge_label}</span>
                                <span style="color:#a78bfa; font-weight:800;
                                             font-size:1.05rem; margin-left:12px;">
                                    {score:.4f}
                                </span>
                            </div>
                        </div>
                        <div class="score-bar-bg">
                            <div class="score-bar-fill" style="width:{score_pct}%;"></div>
                        </div>
                        <p style="color:#a6adc8; margin:0; line-height:1.7; font-size:0.95rem;">
                            {preview}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info(
                "🔍 Nenhum resultado encontrado. "
                "Tente outra busca ou ingira mais documentos pelo painel lateral."
            )

elif search_btn and not query.strip():
    st.warning("⚠️ Digite algo para buscar.")

# Tela inicial
else:
    st.markdown(
        """
        <div style="text-align:center; padding:2.5rem 0; color:#4a5568;">
            <h3 style="color:#6b7280; font-weight:600;">Pronto para buscar</h3>
            <p style="color:#4a5568;">
                Digite uma consulta acima e selecione o modo de busca
            </p>
            <br>
            <div style="display:flex; justify-content:center; gap:1.5rem; flex-wrap:wrap;">
                <div class="example-card">
                    <div style="font-size:1.8rem;">🧠</div>
                    <div style="color:#cdd6f4; font-weight:700; margin:6px 0;">Semântica</div>
                    <div style="color:#6b7280; font-size:0.82rem;">
                        Encontra por significado<br>mesmo sem palavras em comum
                    </div>
                </div>
                <div class="example-card">
                    <div style="font-size:1.8rem;">🔤</div>
                    <div style="color:#cdd6f4; font-weight:700; margin:6px 0;">Palavras-chave</div>
                    <div style="color:#6b7280; font-size:0.82rem;">
                        Algoritmo BM25<br>rápido e preciso
                    </div>
                </div>
                <div class="example-card">
                    <div style="font-size:1.8rem;">⚡</div>
                    <div style="color:#cdd6f4; font-weight:700; margin:6px 0;">Híbrida</div>
                    <div style="color:#6b7280; font-size:0.82rem;">
                        Semântica + BM25<br>o melhor dos dois mundos
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
