<script setup>
import { ref } from 'vue'
import { useChatState } from '../../composables/useChatState'
import ChatHeader from './ChatHeader.vue'
import ChatMessageList from './ChatMessageList.vue'
import ChatInput from './ChatInput.vue'
import PdfViewer from '../documents/PdfViewer.vue'
import BidirectionalCitations from '../shared/BidirectionalCitations.vue'
import QuestionSuggestions from './QuestionSuggestions.vue'

const {
  messages,
  isLoading,
  error,
  isRetrieving,
  showPdfViewer,
  currentPdfUrl,
  currentPdfPage,
  currentHighlightText,
  showBidirectionalPanel,
  selectedCitation,
  bidirectionalIndex,
  selectedCount,
  selectedDocuments,
  hasSelection,
  sendMessage,
  stopGenerating,
  clearConversation,
  handleChunkClick,
  handleChunkRightClick,
  closePdfViewer,
  closeBidirectionalPanel,
  navigateToMessage,
} = useChatState()

const suggestionsRef = ref(null)

const handleSuggestionSelect = async (questionText) => {
  await sendMessage(questionText)
  // After a suggestion-driven question completes, generate a fresh batch
  suggestionsRef.value?.refresh()
}
</script>

<template>
  <div class="panel chat-panel">
    <ChatHeader
      :has-selection="hasSelection"
      :selected-count="selectedCount"
      :selected-documents="selectedDocuments"
      :has-messages="messages.length > 0"
      @clear="clearConversation"
    />

    <ChatMessageList
      :messages="messages"
      :is-loading="isLoading"
      :is-retrieving="isRetrieving"
      :has-selection="hasSelection"
      :selected-documents="selectedDocuments"
      @chunk-click="handleChunkClick"
      @chunk-rightclick="handleChunkRightClick"
      @suggestion-click="handleSuggestionSelect"
    />

    <div v-if="messages.length > 0" class="chat-suggestions-wrap">
      <QuestionSuggestions
        ref="suggestionsRef"
        :selected-documents="selectedDocuments"
        :disabled="isLoading"
        @question-select="handleSuggestionSelect"
      />
    </div>

    <ChatInput
      :is-loading="isLoading"
      @send="sendMessage"
      @stop="stopGenerating"
    />

    <div v-if="error" class="chat-error" role="alert">{{ error }}</div>

    <PdfViewer
      :show="showPdfViewer"
      :pdf-url="currentPdfUrl"
      :target-page="currentPdfPage"
      :highlight-text="currentHighlightText"
      @close="closePdfViewer"
    />

    <BidirectionalCitations
      :show="showBidirectionalPanel"
      :source="selectedCitation.source"
      :page="selectedCitation.page"
      :text="selectedCitation.text"
      :citations="bidirectionalIndex[selectedCitation.source + '_' + selectedCitation.page + '_' + (selectedCitation.text || '').substring(0, 50)] || []"
      @close="closeBidirectionalPanel"
      @navigate-to-message="navigateToMessage"
    />
  </div>
</template>

<style scoped>
@keyframes highlightMessage {
  0% { background: rgba(129, 140, 248, 0.2); }
  100% { background: transparent; }
}

.chat-panel {
  position: relative;
  background: var(--surface);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  min-height: 0;
  height: 100%;
}

.chat-suggestions-wrap {
  padding: 0 16px 4px;
}

.chat-error {
  margin: 0 16px 4px;
  min-height: 1.2em;
  font-size: 12px;
  color: #fca5a5;
}
</style>
