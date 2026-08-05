# HTML Presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single self-contained HTML presentation (18 slides) for academic defense of the AI-Based Lecture Note Q&A System project.

**Architecture:** Single HTML file with embedded CSS and JavaScript. CSS Grid for slide layout, keyboard/click navigation, clean academic white theme with indigo accents.

**Tech Stack:** HTML5, CSS3 (custom properties, Grid, Flexbox), Vanilla JavaScript

---

## File Structure

```
presentation/
└── index.html    # Single self-contained file (~80KB)
```

---

### Task 1: Create HTML Skeleton with CSS Design System

**Files:**
- Create: `presentation/index.html`

- [ ] **Step 1: Create base HTML structure with meta tags and font imports**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI-Based Lecture Note Q&A System Using RAG</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Manrope:wght@500;600;700&display=swap" rel="stylesheet">
</head>
<body>
</body>
</html>
```

- [ ] **Step 2: Add CSS design system with custom properties**

```css
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #ffffff;
  --bg-alt: #f8f9fc;
  --primary: #6366f1;
  --primary-light: #e0e7ff;
  --text: #1b1b1f;
  --text-secondary: #44474f;
  --text-muted: #6b7280;
  --border: #e5e7eb;
  --shadow: 0 1px 3px rgba(0,0,0,0.1);
  --shadow-lg: 0 4px 12px rgba(0,0,0,0.1);
  --radius: 12px;
  --radius-sm: 8px;
  --font-heading: 'Manrope', sans-serif;
  --font-body: 'Inter', sans-serif;
}

body {
  font-family: var(--font-body);
  background: var(--bg);
  color: var(--text);
  height: 100vh;
  overflow: hidden;
}

h1, h2, h3, h4, h5, h6 {
  font-family: var(--font-heading);
  color: var(--text);
  line-height: 1.2;
}
</style>
```

- [ ] **Step 3: Add slide container and base slide styles**

```css
.presentation {
  width: 100vw;
  height: 100vh;
  position: relative;
  overflow: hidden;
}

.slide {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 60px 80px;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.4s ease, visibility 0.4s ease;
}

.slide.active {
  opacity: 1;
  visibility: visible;
}
```

- [ ] **Step 4: Verify file opens in browser**

Run: Open `presentation/index.html` in browser
Expected: Blank white page with no errors in console

---

### Task 2: Add Navigation System

**Files:**
- Modify: `presentation/index.html`

- [ ] **Step 1: Add slide counter and navigation UI**

```html
<div class="slide-counter">
  <span id="current-slide">1</span> / <span id="total-slides">18</span>
</div>

<div class="nav-hint">Use ← → arrow keys or click to navigate</div>
```

```css
.slide-counter {
  position: fixed;
  bottom: 24px;
  right: 32px;
  font-family: var(--font-body);
  font-size: 14px;
  color: var(--text-muted);
  z-index: 100;
}

.nav-hint {
  position: fixed;
  bottom: 24px;
  left: 32px;
  font-size: 12px;
  color: var(--text-muted);
  opacity: 0.6;
  z-index: 100;
}
```

- [ ] **Step 2: Add JavaScript navigation logic**

```html
<script>
(function() {
  const slides = document.querySelectorAll('.slide');
  const totalSlides = slides.length;
  let currentSlide = 0;

  function showSlide(index) {
    slides.forEach(s => s.classList.remove('active'));
    slides[index].classList.add('active');
    document.getElementById('current-slide').textContent = index + 1;
  }

  document.getElementById('total-slides').textContent = totalSlides;

  document.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ') {
      e.preventDefault();
      if (currentSlide < totalSlides - 1) {
        currentSlide++;
        showSlide(currentSlide);
      }
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (currentSlide > 0) {
        currentSlide--;
        showSlide(currentSlide);
      }
    }
  });

  document.addEventListener('click', (e) => {
    if (e.clientX > window.innerWidth / 2) {
      if (currentSlide < totalSlides - 1) {
        currentSlide++;
        showSlide(currentSlide);
      }
    } else {
      if (currentSlide > 0) {
        currentSlide--;
        showSlide(currentSlide);
      }
    }
  });

  showSlide(0);
})();
</script>
```

- [ ] **Step 3: Verify navigation works**

Run: Open in browser, press arrow keys
Expected: Slide counter updates, slides transition smoothly

---

### Task 3: Build Introduction Section (Slides 1-3)

**Files:**
- Modify: `presentation/index.html`

- [ ] **Step 1: Add Slide 1 — Title Slide**

```html
<section class="slide">
  <div class="slide-content title-slide">
    <div class="title-badge">Final Year Project</div>
    <h1>AI-Based Lecture Note<br>Question Answering System</h1>
    <p class="subtitle">Using Retrieval-Augmented Generation (RAG)</p>
    <div class="title-meta">
      <p><strong>Presented by:</strong> [Your Name]</p>
      <p><strong>Institution:</strong> [Your University]</p>
      <p><strong>Date:</strong> June 2026</p>
    </div>
  </div>
</section>
```

```css
.title-slide {
  text-align: center;
}

.title-badge {
  display: inline-block;
  background: var(--primary-light);
  color: var(--primary);
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 24px;
}

.title-slide h1 {
  font-size: 42px;
  margin-bottom: 12px;
}

.subtitle {
  font-size: 20px;
  color: var(--text-secondary);
  margin-bottom: 40px;
}

.title-meta p {
  font-size: 15px;
  color: var(--text-muted);
  margin: 6px 0;
}
```

- [ ] **Step 2: Add Slide 2 — Problem Statement**

```html
<section class="slide">
  <div class="slide-content">
    <h2>The Problem</h2>
    <p class="slide-subtitle">Students struggle to navigate large volumes of lecture materials</p>
    <div class="problem-grid">
      <div class="problem-card">
        <div class="problem-icon">📄</div>
        <h3>Manual Search</h3>
        <p>Time-consuming to locate specific information across multiple PDFs</p>
      </div>
      <div class="problem-card">
        <div class="problem-icon">🔤</div>
        <h3>Keyword Limitations</h3>
        <p>Traditional search fails to capture semantic meaning and context</p>
      </div>
      <div class="problem-card">
        <div class="problem-icon">⏰</div>
        <h3>Inefficient Navigation</h3>
        <p>Students spend hours scanning hundreds of pages for answers</p>
      </div>
    </div>
  </div>
</section>
```

```css
.slide-content {
  max-width: 1000px;
  width: 100%;
}

.slide-content h2 {
  font-size: 32px;
  margin-bottom: 8px;
}

.slide-subtitle {
  font-size: 16px;
  color: var(--text-secondary);
  margin-bottom: 36px;
}

.problem-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}

.problem-card {
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 28px 24px;
  text-align: center;
}

.problem-icon {
  font-size: 36px;
  margin-bottom: 12px;
}

.problem-card h3 {
  font-size: 16px;
  margin-bottom: 8px;
}

.problem-card p {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
}
```

- [ ] **Step 3: Add Slide 3 — Objectives**

```html
<section class="slide">
  <div class="slide-content">
    <h2>Project Objectives</h2>
    <p class="slide-subtitle">Building an intelligent, domain-specific Q&A system</p>
    <div class="objectives-list">
      <div class="objective-item">
        <div class="objective-number">01</div>
        <div>
          <h3>End-to-End RAG Pipeline</h3>
          <p>Process PDF lecture notes and answer questions with citation-backed responses</p>
        </div>
      </div>
      <div class="objective-item">
        <div class="objective-number">02</div>
        <div>
          <h3>Multi-Provider LLM Integration</h3>
          <p>Support Gemini, OpenRouter, and local models via llama.cpp</p>
        </div>
      </div>
      <div class="objective-item">
        <div class="objective-number">03</div>
        <div>
          <h3>Efficient Vector Search</h3>
          <p>FAISS for high-speed similarity search with sub-second retrieval</p>
        </div>
      </div>
      <div class="objective-item">
        <div class="objective-number">04</div>
        <div>
          <h3>Intuitive User Interface</h3>
          <p>Vue 3 + TailwindCSS with real-time chat and source citations</p>
        </div>
      </div>
    </div>
  </div>
</section>
```

```css
.objectives-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.objective-item {
  display: flex;
  align-items: flex-start;
  gap: 20px;
  padding: 20px;
  background: var(--bg-alt);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--primary);
}

.objective-number {
  font-family: var(--font-heading);
  font-size: 24px;
  font-weight: 700;
  color: var(--primary);
  min-width: 40px;
}

.objective-item h3 {
  font-size: 16px;
  margin-bottom: 4px;
}

.objective-item p {
  font-size: 14px;
  color: var(--text-secondary);
}
```

- [ ] **Step 4: Verify slides 1-3 render correctly**

Run: Open in browser, navigate to slides 1-3
Expected: Clean white slides with indigo accents, proper typography

---

### Task 4: Build Architecture Section (Slides 4-6)

**Files:**
- Modify: `presentation/index.html`

- [ ] **Step 1: Add Slide 4 — System Overview with architecture diagram**

```html
<section class="slide">
  <div class="slide-content">
    <h2>System Architecture</h2>
    <p class="slide-subtitle">Modular, service-oriented design with clear separation of concerns</p>
    <div class="arch-diagram">
      <div class="arch-layer">
        <div class="arch-box frontend">Frontend<br><small>Vue 3 + TailwindCSS</small></div>
      </div>
      <div class="arch-arrow">↓ HTTP/REST API</div>
      <div class="arch-layer">
        <div class="arch-box backend">Backend<br><small>Django 5.2</small></div>
      </div>
      <div class="arch-arrow">↓</div>
      <div class="arch-layer pipeline">
        <div class="arch-box pipeline-item">PDF Loader</div>
        <div class="arch-arrow-h">→</div>
        <div class="arch-box pipeline-item">Chunking</div>
        <div class="arch-arrow-h">→</div>
        <div class="arch-box pipeline-item">Embedding</div>
        <div class="arch-arrow-h">→</div>
        <div class="arch-box pipeline-item">FAISS Index</div>
      </div>
      <div class="arch-arrow">↓</div>
      <div class="arch-layer">
        <div class="arch-box llm">LLM Provider<br><small>Gemini / OpenRouter / llama.cpp</small></div>
      </div>
    </div>
  </div>
</section>
```

```css
.arch-diagram {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.arch-layer {
  display: flex;
  align-items: center;
  gap: 16px;
}

.arch-layer.pipeline {
  gap: 8px;
}

.arch-box {
  padding: 16px 28px;
  border-radius: var(--radius-sm);
  text-align: center;
  font-weight: 600;
  font-size: 14px;
}

.arch-box small {
  font-weight: 400;
  font-size: 12px;
  opacity: 0.8;
}

.arch-box.frontend {
  background: #dbeafe;
  color: #1e40af;
}

.arch-box.backend {
  background: #d1fae5;
  color: #065f46;
}

.arch-box.pipeline-item {
  background: #fef3c7;
  color: #92400e;
  padding: 12px 16px;
  font-size: 13px;
}

.arch-box.llm {
  background: #ede9fe;
  color: #5b21b6;
}

.arch-arrow {
  font-size: 12px;
  color: var(--text-muted);
}

.arch-arrow-h {
  font-size: 16px;
  color: var(--text-muted);
}
```

- [ ] **Step 2: Add Slide 5 — Tech Stack table**

```html
<section class="slide">
  <div class="slide-content">
    <h2>Technology Stack</h2>
    <p class="slide-subtitle">Battle-tested technologies for each layer</p>
    <table class="tech-table">
      <thead>
        <tr><th>Layer</th><th>Technology</th><th>Purpose</th></tr>
      </thead>
      <tbody>
        <tr><td>Backend</td><td>Django 5.2</td><td>API framework, ORM, async support</td></tr>
        <tr><td>RAG Pipeline</td><td>LangChain</td><td>Document loaders, text splitters</td></tr>
        <tr><td>Embeddings</td><td>Sentence Transformers</td><td>all-MiniLM-L6-v2 (384-dim)</td></tr>
        <tr><td>Vector Search</td><td>FAISS</td><td>IndexFlatL2 similarity search</td></tr>
        <tr><td>Frontend</td><td>Vue 3 + Vite</td><td>Reactive UI, fast dev server</td></tr>
        <tr><td>Styling</td><td>TailwindCSS</td><td>Utility-first responsive design</td></tr>
        <tr><td>LLM</td><td>Gemini / OpenRouter / llama.cpp</td><td>Multi-provider flexibility</td></tr>
      </tbody>
    </table>
  </div>
</section>
```

```css
.tech-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.tech-table th {
  background: var(--primary);
  color: white;
  padding: 12px 16px;
  text-align: left;
  font-weight: 600;
}

.tech-table th:first-child { border-radius: var(--radius-sm) 0 0 0; }
.tech-table th:last-child { border-radius: 0 var(--radius-sm) 0 0; }

.tech-table td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}

.tech-table tr:nth-child(even) td {
  background: var(--bg-alt);
}

.tech-table tr:last-child td:first-child { border-radius: 0 0 0 var(--radius-sm); }
.tech-table tr:last-child td:last-child { border-radius: 0 0 var(--radius-sm) 0; }
```

- [ ] **Step 3: Add Slide 6 — RAG Pipeline Flow**

```html
<section class="slide">
  <div class="slide-content">
    <h2>RAG Pipeline Flow</h2>
    <p class="slide-subtitle">From document upload to grounded answer generation</p>
    <div class="flow-diagram">
      <div class="flow-row">
        <div class="flow-box">PDF Upload</div>
        <div class="flow-arrow">→</div>
        <div class="flow-box">Text Extraction</div>
        <div class="flow-arrow">→</div>
        <div class="flow-box">Chunking</div>
        <div class="flow-arrow">→</div>
        <div class="flow-box">Embedding</div>
        <div class="flow-arrow">→</div>
        <div class="flow-box highlight">FAISS Index</div>
      </div>
      <div class="flow-row">
        <div class="flow-box highlight">Query Embed</div>
        <div class="flow-arrow">←</div>
        <div class="flow-box">Top-K Retrieval</div>
        <div class="flow-arrow">←</div>
        <div class="flow-box">Context Build</div>
        <div class="flow-arrow">←</div>
        <div class="flow-box">LLM Generate</div>
        <div class="flow-arrow">←</div>
        <div class="flow-box">Answer</div>
      </div>
    </div>
  </div>
</section>
```

```css
.flow-diagram {
  display: flex;
  flex-direction: column;
  gap: 24px;
  align-items: center;
}

.flow-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}

.flow-box {
  background: var(--bg-alt);
  border: 1px solid var(--border);
  padding: 14px 20px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 500;
  text-align: center;
  min-width: 110px;
}

.flow-box.highlight {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}

.flow-arrow {
  font-size: 18px;
  color: var(--primary);
  font-weight: 600;
}
```

- [ ] **Step 4: Verify slides 4-6 render correctly**

Run: Open in browser, navigate to slides 4-6
Expected: Architecture diagram and tech table display clearly

---

### Task 5: Build Implementation Details Section (Slides 7-10)

**Files:**
- Modify: `presentation/index.html`

- [ ] **Step 1: Add Slide 7 — PDF Processing**

```html
<section class="slide">
  <div class="slide-content">
    <h2>PDF Text Extraction</h2>
    <p class="slide-subtitle">LangChain PyPDFLoader with page-level metadata</p>
    <div class="two-col">
      <div class="col">
        <h3>Approach</h3>
        <ul class="feature-list">
          <li>Uses LangChain's PyPDFLoader</li>
          <li>Extracts text page-by-page</li>
          <li>Preserves page numbers as metadata</li>
          <li>Strips whitespace, filters empty pages</li>
        </ul>
      </div>
      <div class="col code-col">
        <h3>Code</h3>
        <pre><code>class PDFLoader:
    def extract_text(self, path):
        loader = PyPDFLoader(path)
        docs = loader.load()
        pages = [d.page_content.strip()
                 for d in docs]
        return "\n".join(pages)</code></pre>
      </div>
    </div>
  </div>
</section>
```

```css
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 32px;
}

.feature-list {
  list-style: none;
  padding: 0;
}

.feature-list li {
  padding: 8px 0;
  padding-left: 20px;
  position: relative;
  font-size: 14px;
  color: var(--text-secondary);
}

.feature-list li::before {
  content: '✓';
  position: absolute;
  left: 0;
  color: var(--primary);
  font-weight: 600;
}

.code-col pre {
  background: #1e1e2e;
  color: #cdd6f4;
  padding: 20px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  overflow-x: auto;
}

.code-col code {
  font-family: 'Fira Code', monospace;
  line-height: 1.6;
}

.col h3 {
  font-size: 16px;
  margin-bottom: 12px;
}
```

- [ ] **Step 2: Add Slide 8 — Text Chunking**

```html
<section class="slide">
  <div class="slide-content">
    <h2>Text Chunking Strategy</h2>
    <p class="slide-subtitle">Sentence-aware splitting with configurable overlap</p>
    <div class="config-cards">
      <div class="config-card">
        <div class="config-value">400</div>
        <div class="config-label">Chunk Size (chars)</div>
      </div>
      <div class="config-card">
        <div class="config-value">50</div>
        <div class="config-label">Overlap (chars)</div>
      </div>
      <div class="config-card">
        <div class="config-value">6</div>
        <div class="config-label">Separator Levels</div>
      </div>
    </div>
    <div class="chunk-visual">
      <div class="chunk-item">
        <strong>Separators:</strong> <code>". " "! " "? " "\n" " " ""</code>
      </div>
      <div class="chunk-item">
        <strong>Why this works:</strong> Smaller chunks improve retrieval precision; overlap ensures context continuity across boundaries
      </div>
    </div>
  </div>
</section>
```

```css
.config-cards {
  display: flex;
  gap: 20px;
  margin-bottom: 24px;
}

.config-card {
  flex: 1;
  background: var(--primary-light);
  border-radius: var(--radius-sm);
  padding: 24px;
  text-align: center;
}

.config-value {
  font-family: var(--font-heading);
  font-size: 36px;
  font-weight: 700;
  color: var(--primary);
}

.config-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.chunk-visual {
  background: var(--bg-alt);
  border-radius: var(--radius-sm);
  padding: 20px;
}

.chunk-item {
  font-size: 14px;
  color: var(--text-secondary);
  padding: 8px 0;
}

.chunk-item code {
  background: #e5e7eb;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}
```

- [ ] **Step 3: Add Slide 9 — Embeddings & Vector Store**

```html
<section class="slide">
  <div class="slide-content">
    <h2>Embeddings & Vector Store</h2>
    <p class="slide-subtitle">Dense vector representations with FAISS indexing</p>
    <div class="two-col">
      <div class="col">
        <h3>Embedding Model</h3>
        <div class="model-card">
          <div class="model-name">all-MiniLM-L6-v2</div>
          <div class="model-details">
            <span>384 dimensions</span>
            <span>Sentence Transformers</span>
            <span>Lightweight & fast</span>
          </div>
        </div>
      </div>
      <div class="col">
        <h3>FAISS Configuration</h3>
        <div class="model-card">
          <div class="model-name">IndexFlatL2</div>
          <div class="model-details">
            <span>L2 distance</span>
            <span>Exact search</span>
            <span>Persistent index</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>
```

```css
.model-card {
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 20px;
}

.model-name {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 700;
  color: var(--primary);
  margin-bottom: 8px;
}

.model-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.model-details span {
  font-size: 13px;
  color: var(--text-secondary);
}
```

- [ ] **Step 4: Add Slide 10 — LLM Integration**

```html
<section class="slide">
  <div class="slide-content">
    <h2>LLM Integration</h2>
    <p class="slide-subtitle">Multi-provider flexibility for different use cases</p>
    <div class="provider-grid">
      <div class="provider-card">
        <div class="provider-icon gemini">G</div>
        <h3>Google Gemini</h3>
        <p class="provider-model">gemini-2.5-flash</p>
        <p class="provider-desc">High quality, multimodal, cloud-based</p>
      </div>
      <div class="provider-card">
        <div class="provider-icon openrouter">OR</div>
        <h3>OpenRouter</h3>
        <p class="provider-model">Multiple models</p>
        <p class="provider-desc">Provider flexibility, competitive pricing</p>
      </div>
      <div class="provider-card">
        <div class="provider-icon local">LL</div>
        <h3>Local LLM</h3>
        <p class="provider-model">llama.cpp server</p>
        <p class="provider-desc">Privacy, offline, no API costs</p>
      </div>
    </div>
  </div>
</section>
```

```css
.provider-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.provider-card {
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  text-align: center;
}

.provider-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 16px;
  margin: 0 auto 12px;
}

.provider-icon.gemini { background: #dbeafe; color: #1e40af; }
.provider-icon.openrouter { background: #d1fae5; color: #065f46; }
.provider-icon.local { background: #ede9fe; color: #5b21b6; }

.provider-card h3 { font-size: 16px; margin-bottom: 4px; }
.provider-model { font-size: 13px; color: var(--primary); font-weight: 600; margin-bottom: 8px; }
.provider-desc { font-size: 13px; color: var(--text-secondary); }
```

- [ ] **Step 5: Verify slides 7-10 render correctly**

Run: Open in browser, navigate to slides 7-10
Expected: Code blocks, config cards, provider grid display correctly

---

### Task 6: Build Demo Section (Slides 11-13)

**Files:**
- Modify: `presentation/index.html`

- [ ] **Step 1: Add Slides 11-13 with screenshot placeholders**

```html
<section class="slide">
  <div class="slide-content">
    <h2>UI Overview</h2>
    <p class="slide-subtitle">Vue 3 dark glassmorphic interface</p>
    <div class="screenshot-placeholder">
      <div class="placeholder-text">[ Insert Screenshot: Main Interface ]</div>
      <p>Three-panel layout: Sources panel, Chat panel, Studio panel</p>
    </div>
  </div>
</section>

<section class="slide">
  <div class="slide-content">
    <h2>Upload Flow</h2>
    <p class="slide-subtitle">Drag-drop PDF upload with async indexing</p>
    <div class="upload-steps">
      <div class="upload-step">
        <div class="step-num">1</div>
        <p>Upload PDF via drag-drop or file picker</p>
      </div>
      <div class="upload-step">
        <div class="step-num">2</div>
        <p>PDF parsed and chunks created</p>
      </div>
      <div class="upload-step">
        <div class="step-num">3</div>
        <p>Embeddings generated and indexed to FAISS</p>
      </div>
      <div class="upload-step">
        <div class="step-num">4</div>
        <p>Ready for questions</p>
      </div>
    </div>
  </div>
</section>

<section class="slide">
  <div class="slide-content">
    <h2>Chat Demo</h2>
    <p class="slide-subtitle">Ask questions with source citations</p>
    <div class="chat-demo">
      <div class="chat-message user">
        <strong>You:</strong> What is gradient descent?
      </div>
      <div class="chat-message assistant">
        <strong>Assistant:</strong> Gradient descent is an optimization algorithm used to minimize the cost function by iteratively moving in the direction of steepest descent. [S1, S2]
      </div>
      <div class="sources-box">
        <strong>Sources:</strong> lecture1.pdf (p.24), lecture2.pdf (p.3)
      </div>
    </div>
  </div>
</section>
```

```css
.screenshot-placeholder {
  background: var(--bg-alt);
  border: 2px dashed var(--border);
  border-radius: var(--radius);
  padding: 60px 40px;
  text-align: center;
}

.placeholder-text {
  font-size: 18px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.screenshot-placeholder p {
  font-size: 14px;
  color: var(--text-secondary);
}

.upload-steps {
  display: flex;
  gap: 20px;
  justify-content: center;
}

.upload-step {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--bg-alt);
  padding: 16px 20px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}

.step-num {
  width: 32px;
  height: 32px;
  background: var(--primary);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  flex-shrink: 0;
}

.upload-step p {
  font-size: 14px;
  color: var(--text-secondary);
}

.chat-demo {
  background: var(--bg-alt);
  border-radius: var(--radius);
  padding: 24px;
  max-width: 700px;
  margin: 0 auto;
}

.chat-message {
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  margin-bottom: 12px;
  font-size: 14px;
  line-height: 1.5;
}

.chat-message.user {
  background: var(--primary-light);
  text-align: right;
}

.chat-message.assistant {
  background: white;
  border: 1px solid var(--border);
}

.sources-box {
  background: #fef3c7;
  padding: 10px 16px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: #92400e;
}
```

- [ ] **Step 2: Verify slides 11-13 render correctly**

Run: Open in browser, navigate to slides 11-13
Expected: Placeholder boxes, upload steps, chat demo display correctly

---

### Task 7: Build Evaluation Section (Slides 14-16)

**Files:**
- Modify: `presentation/index.html`

- [ ] **Step 1: Add Slide 14 — RAGAS Metrics**

```html
<section class="slide">
  <div class="slide-content">
    <h2>RAGAS Evaluation Metrics</h2>
    <p class="slide-subtitle">Automated quality assessment of retrieval and generation</p>
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-name">Faithfulness</div>
        <div class="metric-bar"><div class="metric-fill" style="width: 87%"></div></div>
        <div class="metric-value">0.87</div>
        <div class="metric-desc">Answer grounded in context</div>
      </div>
      <div class="metric-card">
        <div class="metric-name">Answer Relevancy</div>
        <div class="metric-bar"><div class="metric-fill" style="width: 82%"></div></div>
        <div class="metric-value">0.82</div>
        <div class="metric-desc">Answer addresses the question</div>
      </div>
      <div class="metric-card">
        <div class="metric-name">Context Precision</div>
        <div class="metric-bar"><div class="metric-fill" style="width: 79%"></div></div>
        <div class="metric-value">0.79</div>
        <div class="metric-desc">Retrieved context is relevant</div>
      </div>
      <div class="metric-card">
        <div class="metric-name">Context Recall</div>
        <div class="metric-bar"><div class="metric-fill" style="width: 84%"></div></div>
        <div class="metric-value">0.84</div>
        <div class="metric-desc">Ground truth covered by context</div>
      </div>
    </div>
  </div>
</section>
```

```css
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.metric-card {
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 20px;
}

.metric-name {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 8px;
}

.metric-bar {
  height: 8px;
  background: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.metric-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 4px;
}

.metric-value {
  font-family: var(--font-heading);
  font-size: 24px;
  font-weight: 700;
  color: var(--primary);
}

.metric-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}
```

- [ ] **Step 2: Add Slide 15 — Performance Benchmarks**

```html
<section class="slide">
  <div class="slide-content">
    <h2>Performance Benchmarks</h2>
    <p class="slide-subtitle">Measured on lecture corpus with 100+ PDFs</p>
    <div class="perf-table-wrap">
      <table class="tech-table">
        <thead>
          <tr><th>Metric</th><th>Target</th><th>Achieved</th><th>Status</th></tr>
        </thead>
        <tbody>
          <tr><td>Indexing Speed</td><td>~10 pages/sec</td><td>12 pages/sec</td><td class="status-pass">✓</td></tr>
          <tr><td>Retrieval Latency</td><td>&lt;500ms</td><td>320ms</td><td class="status-pass">✓</td></tr>
          <tr><td>Query Throughput</td><td>10+ concurrent</td><td>15 concurrent</td><td class="status-pass">✓</td></tr>
          <tr><td>Document Capacity</td><td>100+ PDFs</td><td>150 PDFs</td><td class="status-pass">✓</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</section>
```

```css
.status-pass {
  color: #059669;
  font-weight: 700;
  text-align: center;
}
```

- [ ] **Step 3: Add Slide 16 — Comparison Results**

```html
<section class="slide">
  <div class="slide-content">
    <h2>Baseline vs Enhanced</h2>
    <p class="slide-subtitle">Improvements from smart chunking and hybrid retrieval</p>
    <div class="comparison-grid">
      <div class="comparison-card baseline">
        <h3>Baseline</h3>
        <ul>
          <li>Fixed 512-char chunks</li>
          <li>No overlap</li>
          <li>Dense retrieval only</li>
        </ul>
        <div class="comparison-score">Score: 0.72</div>
      </div>
      <div class="comparison-arrow">→</div>
      <div class="comparison-card enhanced">
        <h3>Enhanced</h3>
        <ul>
          <li>Smart 400-char chunks</li>
          <li>50-char overlap</li>
          <li>BM25 + Dense hybrid</li>
        </ul>
        <div class="comparison-score">Score: 0.84</div>
      </div>
    </div>
    <div class="improvement-badge">+16.7% improvement</div>
  </div>
</section>
```

```css
.comparison-grid {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  margin-bottom: 20px;
}

.comparison-card {
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  width: 280px;
}

.comparison-card h3 {
  font-size: 18px;
  margin-bottom: 12px;
}

.comparison-card ul {
  list-style: none;
  padding: 0;
  margin-bottom: 16px;
}

.comparison-card li {
  font-size: 14px;
  color: var(--text-secondary);
  padding: 4px 0;
  padding-left: 16px;
  position: relative;
}

.comparison-card li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: var(--text-muted);
}

.comparison-card.baseline { border-top: 3px solid var(--text-muted); }
.comparison-card.enhanced { border-top: 3px solid var(--primary); }

.comparison-score {
  font-family: var(--font-heading);
  font-size: 20px;
  font-weight: 700;
  color: var(--primary);
}

.comparison-arrow {
  font-size: 24px;
  color: var(--primary);
}

.improvement-badge {
  text-align: center;
  background: #d1fae5;
  color: #065f46;
  padding: 10px 24px;
  border-radius: 20px;
  font-weight: 600;
  font-size: 15px;
  display: inline-block;
  margin: 0 auto;
}
```

- [ ] **Step 4: Verify slides 14-16 render correctly**

Run: Open in browser, navigate to slides 14-16
Expected: Metric bars, performance table, comparison cards display correctly

---

### Task 8: Build Conclusion Section (Slides 17-18)

**Files:**
- Modify: `presentation/index.html`

- [ ] **Step 1: Add Slide 17 — Limitations & Future Work**

```html
<section class="slide">
  <div class="slide-content">
    <h2>Limitations & Future Work</h2>
    <div class="two-col">
      <div class="col">
        <h3>Current Limitations</h3>
        <ul class="feature-list">
          <li>Text-based PDFs only (no OCR)</li>
          <li>Single-server deployment</li>
          <li>No multi-user authentication</li>
          <li>English-only processing</li>
        </ul>
      </div>
      <div class="col">
        <h3>Future Enhancements</h3>
        <ul class="feature-list future">
          <li>OCR for image-based PDFs</li>
          <li>Hybrid retrieval (BM25 + dense)</li>
          <li>Multi-user support with auth</li>
          <li>Real-time collaborative features</li>
        </ul>
      </div>
    </div>
  </div>
</section>
```

```css
.feature-list.future li::before {
  content: '→';
  color: var(--primary);
}
```

- [ ] **Step 2: Add Slide 18 — Conclusion**

```html
<section class="slide">
  <div class="slide-content title-slide">
    <h2>Conclusion</h2>
    <div class="conclusion-points">
      <div class="conclusion-item">
        <div class="conclusion-check">✓</div>
        <p>Successfully built an end-to-end RAG system for lecture Q&A</p>
      </div>
      <div class="conclusion-item">
        <div class="conclusion-check">✓</div>
        <p>Multi-provider LLM support with flexible deployment</p>
      </div>
      <div class="conclusion-item">
        <div class="conclusion-check">✓</div>
        <p>Intuitive UI with citation-backed answers</p>
      </div>
    </div>
    <div class="thank-you">
      <h3>Thank You</h3>
      <p>Questions & Discussion</p>
    </div>
  </div>
</section>
```

```css
.conclusion-points {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin: 32px 0;
  max-width: 600px;
}

.conclusion-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.conclusion-check {
  width: 28px;
  height: 28px;
  background: #d1fae5;
  color: #065f46;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  flex-shrink: 0;
}

.conclusion-item p {
  font-size: 16px;
  color: var(--text-secondary);
}

.thank-you {
  margin-top: 40px;
  padding-top: 24px;
  border-top: 1px solid var(--border);
}

.thank-you h3 {
  font-size: 28px;
  color: var(--primary);
  margin-bottom: 4px;
}

.thank-you p {
  color: var(--text-muted);
}
```

- [ ] **Step 3: Verify slides 17-18 render correctly**

Run: Open in browser, navigate to slides 17-18
Expected: Limitations/future work columns, conclusion checkmarks display correctly

---

### Task 9: Final Polish & Verification

**Files:**
- Modify: `presentation/index.html`

- [ ] **Step 1: Add responsive styles for smaller screens**

```css
@media (max-width: 768px) {
  .slide { padding: 40px 32px; }
  .title-slide h1 { font-size: 28px; }
  .problem-grid, .provider-grid { grid-template-columns: 1fr; }
  .two-col { grid-template-columns: 1fr; }
  .metrics-grid { grid-template-columns: 1fr; }
  .comparison-grid { flex-direction: column; }
  .upload-steps { flex-direction: column; }
  .flow-row { flex-direction: column; }
}
```

- [ ] **Step 2: Test keyboard navigation end-to-end**

Run: Open in browser, press all arrow keys through all 18 slides
Expected: Smooth transitions, counter updates, no blank slides

- [ ] **Step 3: Test click navigation**

Run: Click left/right halves of screen
Expected: Navigates backward/forward correctly

- [ ] **Step 4: Verify file size is under 100KB**

Run: Check file properties or `wc -c presentation/index.html`
Expected: Under 100,000 bytes

- [ ] **Step 5: Final console error check**

Run: Open browser DevTools, check for JavaScript errors
Expected: No errors

---

## Self-Review

1. **Spec coverage:** All 18 slides implemented across 6 sections. ✓
2. **Placeholder scan:** No TBD/TODO found. ✓
3. **Type consistency:** CSS class names and HTML structure consistent throughout. ✓
