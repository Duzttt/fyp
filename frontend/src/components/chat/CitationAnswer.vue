<script setup>
import { ref, computed, onMounted } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import BaseTooltip from '../shared/BaseTooltip.vue'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true
})

const renderMarkdown = (text) => {
  if (!text) return ''
  return DOMPurify.sanitize(md.renderInline(text))
}

const props = defineProps({
  /**
   * Array of sentences with citations:
   * [{ text: "...", citations: [1, 2] }, ...]
   */
  sentences: {
    type: Array,
    default: () => [],
  },
  /**
   * Sources map by chunk ID:
   * { "1": { file: "lecture.pdf", page: 24 }, ... }
   */
  sources: {
    type: Object,
    default: () => ({}),
  },
  /**
   * Whether to show the tooltip on hover
   */
  showTooltip: {
    type: Boolean,
    default: true,
  },
})

const activeTooltip = ref(null)
const tooltipPosition = ref({ x: 0, y: 0 })
const tooltipTriggerRef = ref(null)
const WORD_TOKEN_RE = /[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?/g
const STOP_WORDS = new Set([
  'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'in', 'into',
  'is', 'it', 'its', 'of', 'on', 'or', 'that', 'the', 'their', 'this', 'to',
  'was', 'were', 'with',
])

/**
 * Get source info for a citation ID
 */
const getSourceInfo = (citationId) => {
  const idStr = String(citationId)
  return props.sources[idStr] || null
}

/**
 * Get multiple source infos for citation array
 */
const getSourceInfos = (citationIds) => {
  return citationIds
    .map((id) => ({ id, info: getSourceInfo(id) }))
    .filter((item) => item.info !== null)
}

/**
 * Check if a sentence has citations
 */
const hasCitations = (sentence) => {
  return sentence.citations && sentence.citations.length > 0
}

const tokenizeWords = (text) => {
  if (!text) return []

  return Array.from(text.matchAll(WORD_TOKEN_RE))
    .map((match) => {
      const raw = match[0]
      const normalized = raw.toLowerCase().replace(/[^a-z0-9]+/g, '')
      if (!normalized) return null

      return {
        raw,
        normalized,
        start: match.index,
        end: match.index + raw.length,
      }
    })
    .filter(Boolean)
}

const chunkWordCache = computed(() => {
  const cache = new Map()

  Object.entries(props.sources).forEach(([id, info]) => {
    const normalizedWords = tokenizeWords(info?.text || '')
      .map((token) => token.normalized)
      .join(' ')
    cache.set(id, ` ${normalizedWords} `)
  })

  return cache
})

const shouldHighlightPhrase = (phraseWords) => {
  if (phraseWords.length === 0) return false

  const nonStopWords = phraseWords.filter((word) => !STOP_WORDS.has(word))
  if (phraseWords.length === 1) {
    return nonStopWords.length === 1 && phraseWords[0].length >= 8
  }

  return nonStopWords.length >= 2 && phraseWords.join(' ').length >= 12
}

const getEvidenceSpans = (sentence) => {
  if (!hasCitations(sentence)) return []

  const wordTokens = tokenizeWords(sentence.text)
  if (wordTokens.length === 0) return []

  const chunkTexts = sentence.citations
    .map((id) => chunkWordCache.value.get(String(id)))
    .filter(Boolean)

  if (chunkTexts.length === 0) return []

  const spans = []
  let startIndex = 0

  while (startIndex < wordTokens.length) {
    let matchedLength = 0
    const maxLength = Math.min(12, wordTokens.length - startIndex)

    for (let length = maxLength; length >= 1; length -= 1) {
      const phraseWords = wordTokens
        .slice(startIndex, startIndex + length)
        .map((token) => token.normalized)

      if (!shouldHighlightPhrase(phraseWords)) {
        continue
      }

      const phrase = ` ${phraseWords.join(' ')} `
      const hasMatch = chunkTexts.some((chunkText) => chunkText.includes(phrase))
      if (hasMatch) {
        matchedLength = length
        break
      }
    }

    if (matchedLength > 0) {
      const firstToken = wordTokens[startIndex]
      const lastToken = wordTokens[startIndex + matchedLength - 1]
      spans.push({
        start: firstToken.start,
        end: lastToken.end,
      })
      startIndex += matchedLength
      continue
    }

    startIndex += 1
  }

  return spans
}

const getSentenceSegments = (sentence) => {
  const spans = getEvidenceSpans(sentence)
  if (spans.length === 0) {
    return [{ text: sentence.text, matched: false }]
  }

  const segments = []
  let cursor = 0

  spans.forEach((span) => {
    if (span.start > cursor) {
      segments.push({
        text: sentence.text.slice(cursor, span.start),
        matched: false,
      })
    }

    segments.push({
      text: sentence.text.slice(span.start, span.end),
      matched: true,
    })
    cursor = span.end
  })

  if (cursor < sentence.text.length) {
    segments.push({
      text: sentence.text.slice(cursor),
      matched: false,
    })
  }

  return segments
}

const sentenceSegmentsCache = computed(() => {
  return props.sentences.map((sentence) => getSentenceSegments(sentence))
})

/**
 * Format file name for display (just the base name)
 */
const formatFileName = (fileName) => {
  if (!fileName) return 'Unknown'
  const parts = fileName.split('/')
  return parts[parts.length - 1]
}

/**
 * Handle mouse enter on a cited sentence
 */
const handleMouseEnter = (event, sentence, index) => {
  if (!props.showTooltip || !hasCitations(sentence)) return

  tooltipTriggerRef.value = event.currentTarget
  activeTooltip.value = index
}

/**
 * Handle mouse leave on a cited sentence
 */
const handleMouseLeave = () => {
  activeTooltip.value = null
}

/**
 * Get citation label for a sentence (e.g., [1, 2])
 */
const getCitationLabel = (citations) => {
  if (!citations || citations.length === 0) return ''
  return `[${citations.join(', ')}]`
}
</script>

<template>
  <div class="citation-answer">
    <p class="answer-paragraph">
      <span
        v-for="(sentence, idx) in sentences"
        :key="idx"
        class="sentence"
        :class="{ 'has-citations': hasCitations(sentence) }"
        @mouseenter="handleMouseEnter($event, sentence, idx)"
        @mouseleave="handleMouseLeave"
      >
        <template v-for="(segment, segmentIdx) in sentenceSegmentsCache[idx]" :key="`${idx}-${segmentIdx}`">
          <span
            :class="{ 'retrieved-phrase': segment.matched }"
            v-html="renderMarkdown(segment.text)"
          />
        </template>
        <sup v-if="hasCitations(sentence)" class="citation-marker">
          {{ getCitationLabel(sentence.citations) }}
        </sup>
      </span>
    </p>

    <!-- Tooltip -->
    <BaseTooltip
      :show="showTooltip && activeTooltip !== null && !!sentences[activeTooltip]"
      :trigger-ref="tooltipTriggerRef"
      :max-width="320"
      @close="activeTooltip = null"
    >
      <div class="base-tooltip-header">
        <span>📚</span>
        <span>
          {{ sentences[activeTooltip]?.citations.length === 1 ? 'Source' : 'Sources' }}
        </span>
      </div>
      <div class="base-tooltip-content">
        <div
          v-for="{ id, info } in getSourceInfos(sentences[activeTooltip]?.citations || [])"
          :key="id"
          class="tooltip-source-item"
        >
          <span class="source-file" :title="info.file">
            {{ formatFileName(info.file) }}
          </span>
          <span v-if="info.page !== null && info.page !== undefined" class="source-page">
            (p. {{ info.page }})
          </span>
        </div>
      </div>
    </BaseTooltip>
  </div>
</template>

<style scoped>
.citation-answer {
  width: 100%;
}

.answer-paragraph {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-main);
  margin: 0;
}

/* Markdown styling within citation answer */
.citation-answer :deep(strong) {
  font-weight: 600;
  color: var(--text-main);
}

.citation-answer :deep(em) {
  font-style: italic;
}

.citation-answer :deep(code) {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 0.9em;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(129, 140, 248, 0.1);
  color: rgba(129, 140, 248, 0.9);
}

.citation-answer :deep(a) {
  color: var(--accent, #6366f1);
  text-decoration: none;
}

.citation-answer :deep(a:hover) {
  text-decoration: underline;
}

.citation-answer :deep(del) {
  text-decoration: line-through;
  opacity: 0.7;
}

.sentence {
  transition: all 0.2s ease;
  padding: 1px 0;
}

.sentence.has-citations {
  cursor: pointer;
}

.sentence.has-citations:hover {
  background: rgba(99, 102, 241, 0.1);
  border-radius: 2px;
}

.retrieved-phrase {
  text-decoration: underline;
  text-decoration-style: dotted;
  text-decoration-thickness: 1px;
  text-underline-offset: 2px;
  text-decoration-color: rgba(129, 140, 248, 0.9);
}

.citation-marker {
  font-size: 10px;
  color: var(--accent);
  font-weight: 600;
  margin-left: 2px;
  vertical-align: super;
}

/* Tooltip source styles (BaseTooltip handles container) */
.tooltip-source-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: white;
  padding: 4px 6px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
}

.source-file {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
}

.source-page {
  color: var(--accent);
  font-weight: 600;
  font-size: 10px;
  white-space: nowrap;
}
</style>
