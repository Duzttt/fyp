# frontend/src/components/ — Vue Components

All Vue single-file components organized by feature domain.

## Folders

### `admin/`
Admin dashboard for system management.
- `AdminDashboard.vue` — Main admin panel
- `AdminHeader.vue` — Admin header bar
- `TabNav.vue` — Tab navigation

### `chat/`
Chat interface for asking questions and viewing answers.
- `ChatPanel.vue` — Main chat container
- `ChatInput.vue` — Question input field
- `ChatMessage.vue` — Single message bubble
- `ChatMessageList.vue` — Message list container
- `ChatHeader.vue` — Chat header with controls
- `CitationAnswer.vue` — Answer with inline citations
- `QuestionSuggestions.vue` — Auto-generated follow-up questions
- `RetrievalChunks.vue` — Retrieved document chunks display
- `RetrievalScopeIndicator.vue` — Shows active retrieval scope

### `dashboard/`
Analytics and system monitoring.
- `DashboardPanel.vue` — Main dashboard container
- `DashboardHeader.vue` — Dashboard header
- `DashboardStats.vue` — Key metrics display
- `DashboardCharts.vue` — Charts and graphs
- `DashboardConfig.vue` — Dashboard configuration
- `IndexingProgress.vue` — PDF indexing progress tracker
- `ModelComparison.vue` — LLM/embedding model comparison

### `documents/`
Document management and viewing.
- `PdfViewer.vue` — PDF document viewer
- `ComparisonView.vue` — Side-by-side document comparison

### `layout/`
Layout panels and navigation.
- `Topbar.vue` — Top navigation bar
- `SourcesPanel.vue` — Document sources sidebar
- `StudioPanel.vue` — Studio/tools sidebar

### `settings/`
System settings UI.
- `SettingsModal.vue` — Settings dialog (LLM provider, model selection)
- `EmbeddingModelSelector.vue` — Embedding model picker

### `shared/`
Reusable cross-feature components.
- `BidirectionalCitations.vue` — Citation linking between answer and source

### `studio/`
Document analysis tools.
- `SummaryModal.vue` — Summary generation dialog
- `SummaryViewer.vue` — Summary display
