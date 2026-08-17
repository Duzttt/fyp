## Abstract (English)

> **状态：草稿（Draft）** — 基于 Ch1–6 内容撰写，篇幅约 250 词。请按 template 每份文档实际字数上限微调。

Students using lecture-note PDFs as their primary study material often struggle to
locate specific information across large, unstructured documents. Manual keyword
search is slow, and generic search tools cannot answer concept-level questions
that require connecting knowledge across multiple sections. This project develops
an AI-based Lecture-Note Question-Answering (Q&A) System using Retrieval-Augmented
Generation (RAG) to let students query their lecture notes in natural language and
receive accurate, source-grounded answers with page-level citations.

The system follows a layered architecture. A PDF ingestion and smart chunking
pipeline splits lecture notes into semantically coherent segments, which are
embedded with a sentence-transformer model and indexed in a FAISS vector store.
To improve retrieval quality, the system combines dense vector search with BM25
keyword search through Reciprocal Rank Fusion, and applies a lightweight
cross-encoder reranker to refine the candidate list. A unified large-language-model
client supports multiple providers — Google Gemini, OpenRouter, and local
llama.cpp models — enabling citation-aware answer generation over the retrieved
context. A Vue 3 front end provides chat, document management, dashboard, and
study-tool interfaces (summarisation, question suggestions, quizzes, and
flashcards) backed by a Django REST API.

Evaluation was conducted in two layers. Retrieval metrics showed that hybrid
retrieval raised Recall@5 by ~13% and MRR by ~17% over a dense-only baseline, while
the selected reranker achieved the highest MRR (0.94) within an 84 ms p95 latency.
End-to-end RAGAS evaluation measured Faithfulness (~0.65), Answer Relevancy
(~0.80), Context Precision (~0.53), and Context Recall (~0.58). The results show
the system retrieves documents accurately and answers questions within interactive
latency, with retrieval quality as its strongest aspect and answer faithfulness
the clearest opportunity for future improvement.

**Keywords:** Retrieval-Augmented Generation; Hybrid Retrieval; FAISS; Lecture
Notes; Question Answering; Large Language Models

---

## ABSTRAK (Bahasa Melayu)

> **状态：草稿（Draft）** — 以下为英文版直译草稿。**请由马来语母语使用者核对校正语法与术语**，
> 因为马来语非草稿撰写者的母语。正式提交前务必用母语者审校。

Pelajar yang menggunakan nota kuliah dalam bentuk PDF sebagai bahan rujukan utama
sering menghadapi kesukaran untuk mencari maklumat tertentu dalam dokumen yang
besar dan kurang berstruktur. Carian kata kunci secara manual adalah perlahan, dan
alat carian generik tidak dapat menjawab soalan peringkat konsep yang memerlukan
penghubung pengetahuan merentas beberapa bahagian. Projek ini membangunkan Sistem
Soal-Jawab (Q&A) Nota Kuliah berasaskan Kepintaran Buatan (AI) menggunakan
Retrieval-Augmented Generation (RAG) untuk membolehkan pelajar membuat pertanyaan
ke atas nota kuliah dalam bahasa semula jadi dan menerima jawapan yang tepat serta
berasaskan sumber dengan petikan pada tingkat muka surat.

Sistem ini mengikut seni bina berlapis. Paip tanggung-pemprosesan (ingestion) PDF
dan pemecahan pintar (smart chunking) membahagikan nota kuliah kepada segmen yang
koheren dari segi semantik, yang kemudiannya dibenamkan (embedded) dengan model
sentence-transformer dan diindeks dalam stor vektor FAISS. Untuk meningkatkan
kualiti capaian, sistem menggabungkan carian vektor padat (dense) dengan carian
kata kunci BM25 melalui Gabungan Angka Saling (Reciprocal Rank Fusion), dan
menggunakan ranger silang-encoder yang ringan untuk memperhalusi senarai calon.
Klien model bahasa besar yang bersatu menyokong pelbagai pembekal — Google Gemini,
OpenRouter, dan model llama.cpp tempatan — yang membolehkan penjanaan jawapan
berasaskan sumber atas konteks yang dicapai. Antara muka Vue 3 menyediakan sembang,
pengurusan dokumen, papan pemuka, serta antara muka alat kajian (ringkasan, cadangan
soalan, kuiz, dan kad kilat) yang disokong oleh API REST Django.

Penilaian dijalankan dalam dua lapisan. Metrik capaian menunjukkan bahawa capaian
hibrid meningkatkan Recall@5 sebanyak ~13% dan MRR sebanyak ~17% berbanding garis
asas dense sahaja, manakala ranger yang dipilih mencapai MRR tertinggi (0.94)
dalam latensi p95 selama 84 ms. Penilaian RAGAS hujung-ke-hujung mengukur
Faithfulness (~0.65), Answer Relevancy (~0.80), Context Precision (~0.53), dan
Context Recall (~0.58). Hasil menunjukkan sistem ini mencapai semula dokumen dengan
tepat dan menjawab soalan dalam latensi interaktif, dengan kualiti capaian sebagai
aspek terkuat dan kepatuhan jawapan sebagai peluang peningkatan paling jelas pada
masa hadapan.

**Kata kunci:** Retrieval-Augmented Generation; Capaian Hibrid; FAISS; Nota Kuliah;
Soal-Jawab; Model Bahasa Besar
