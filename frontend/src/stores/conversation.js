import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  createConversation,
  deleteConversations,
  listConversations,
  listMessages,
  updateConversation
} from '../api/chat'

export const useConversationStore = defineStore('conversation', () => {
  const conversations = ref([])
  const currentId = ref(null)
  const current = ref(null)
  const messages = ref([])

  async function loadConversations() {
    const data = await listConversations()
    conversations.value = data.conversations || []
  }

  async function create(title) {
    const data = await createConversation(title || '未命名会话')
    await loadConversations()
    await select(data.conversation_id)
    return data
  }

  async function remove(ids) {
    const data = await deleteConversations(ids)
    if (currentId.value && ids.includes(currentId.value)) clear()
    await loadConversations()
    return data
  }

  async function rename(id, title) {
    await updateConversation(id, title)
    await loadConversations()
    if (current.value && current.value.conversation_id === id) current.value.title = title
  }

  async function select(id) {
    const data = await listMessages(id)
    currentId.value = id
    current.value = data.conversation
    messages.value = data.messages
    return data
  }

  function clear() {
    currentId.value = null
    current.value = null
    messages.value = []
  }

  return {
    conversations,
    currentId,
    current,
    messages,
    loadConversations,
    create,
    remove,
    rename,
    select,
    clear
  }
})
