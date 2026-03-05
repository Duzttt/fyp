import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useDocumentStore = defineStore('documents', () => {
  // State
  const selectedDocIds = ref([])
  const allDocuments = ref([])
  const showSelectionPanel = ref(true)

  // Getters
  const selectedCount = computed(() => selectedDocIds.value.length)
  
  const hasSelection = computed(() => selectedDocIds.value.length > 0)
  
  const allSelected = computed(() => {
    if (allDocuments.value.length === 0) return false
    return selectedDocIds.value.length === allDocuments.value.length
  })
  
  const selectedDocuments = computed(() => {
    return allDocuments.value.filter(doc => 
      selectedDocIds.value.includes(doc.name || doc.filename)
    )
  })

  // Actions
  function setAllDocuments(docs) {
    allDocuments.value = docs || []
    // If no selection yet, select all by default
    if (selectedDocIds.value.length === 0 && allDocuments.value.length > 0) {
      selectedDocIds.value = allDocuments.value.map(doc => doc.name || doc.filename)
    }
  }

  function toggleDocSelection(docName) {
    if (!docName) return
    
    const idx = selectedDocIds.value.indexOf(docName)
    if (idx === -1) {
      // Add to selection
      selectedDocIds.value.push(docName)
    } else {
      // Remove from selection
      selectedDocIds.value.splice(idx, 1)
    }
  }

  function selectDoc(docName) {
    if (!docName) return
    if (!selectedDocIds.value.includes(docName)) {
      selectedDocIds.value.push(docName)
    }
  }

  function deselectDoc(docName) {
    if (!docName) return
    const idx = selectedDocIds.value.indexOf(docName)
    if (idx > -1) {
      selectedDocIds.value.splice(idx, 1)
    }
  }

  function isDocSelected(docName) {
    return selectedDocIds.value.includes(docName)
  }

  function toggleSelectAll() {
    if (allSelected.value) {
      // Deselect all
      selectedDocIds.value = []
    } else {
      // Select all
      selectedDocIds.value = allDocuments.value.map(doc => doc.name || doc.filename)
    }
  }

  function setSelectedDocs(docNames) {
    selectedDocIds.value = docNames || []
  }

  function clearSelection() {
    selectedDocIds.value = []
  }

  function selectAll() {
    selectedDocIds.value = allDocuments.value.map(doc => doc.name || doc.filename)
  }

  // Get selected document names for API calls
  function getSelectedSources() {
    return [...selectedDocIds.value]
  }

  return {
    // State
    selectedDocIds,
    allDocuments,
    showSelectionPanel,
    // Getters
    selectedCount,
    hasSelection,
    allSelected,
    selectedDocuments,
    // Actions
    setAllDocuments,
    toggleDocSelection,
    selectDoc,
    deselectDoc,
    isDocSelected,
    toggleSelectAll,
    setSelectedDocs,
    clearSelection,
    selectAll,
    getSelectedSources,
  }
})
