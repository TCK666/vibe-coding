import { ref } from 'vue'
import { defineStore } from 'pinia'
import request from '../api/request'

// 聊天实时通道：ws-token → WebSocket → 8 类事件分发 → 流式状态
// 断线自动重连（指数不做，固定 2s，最多 5 次）；切换会话由 Workbench 调 connect()
export const useChatStore = defineStore('chat', () => {
  const connected = ref(false)
  const taskState = ref(null) // { taskId, status, currentStep, error, resultId }
  const streamingText = ref('')
  const toolEvents = ref([]) // [{ name, status: running|done, summary }]
  const lastError = ref('')

  let ws = null
  let currentConvId = null
  let reconnectTimer = null
  let reconnectTries = 0
  let closedByUs = false
  let doneHandler = null

  function setDoneHandler(fn) {
    doneHandler = fn
  }

  async function connect(conversationId) {
    disconnect(false)
    currentConvId = conversationId
    try {
      const r = await request.post('/api/chat/ws-token', { conversation_id: conversationId })
      const { websocket_token } = r.data.data
      openSocket(conversationId, websocket_token)
    } catch (e) {
      scheduleReconnect()
    }
  }

  function openSocket(conversationId, token) {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    ws = new WebSocket(
      `${proto}://${location.host}/api/chat/ws/chat?websocket_token=${encodeURIComponent(token)}&conversation_id=${conversationId}`
    )
    ws.onopen = () => {
      connected.value = true
      reconnectTries = 0
    }
    ws.onmessage = (e) => {
      try {
        handleEvent(JSON.parse(e.data))
      } catch {
        /* 忽略坏帧 */
      }
    }
    ws.onclose = () => {
      connected.value = false
      if (!closedByUs && currentConvId) scheduleReconnect()
    }
    ws.onerror = () => {}
  }

  function scheduleReconnect() {
    if (reconnectTimer || !currentConvId || reconnectTries >= 5) return
    reconnectTries += 1
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect(currentConvId)
    }, 2000)
  }

  function disconnect(byUs = true) {
    closedByUs = byUs
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      try {
        ws.close()
      } catch {
        /* noop */
      }
      ws = null
    }
    connected.value = false
    resetRound()
  }

  function resetRound() {
    taskState.value = null
    streamingText.value = ''
    toolEvents.value = []
  }

  function handleEvent(ev) {
    const d = ev.data || {}
    switch (ev.type) {
      case 'message_start':
        taskState.value = { taskId: d.task_id, status: 'running', currentStep: '', error: '' }
        streamingText.value = ''
        toolEvents.value = []
        break
      case 'message_delta':
        streamingText.value += d.delta_text || ''
        break
      case 'tool_start':
        toolEvents.value.push({ name: d.tool_name, status: 'running', summary: '' })
        break
      case 'tool_finish': {
        const t = [...toolEvents.value]
          .reverse()
          .find((x) => x.name === d.tool_name && x.status === 'running')
        if (t) {
          t.status = 'done'
          t.summary = d.tool_result_summary || ''
        }
        break
      }
      case 'task_status':
        if (taskState.value) {
          taskState.value.status = d.task_status
          taskState.value.currentStep = d.current_step || ''
        }
        break
      case 'result_ready':
        if (taskState.value) taskState.value.resultId = d.result_id
        break
      case 'error':
        lastError.value = d.error_message || '未知错误'
        if (taskState.value) taskState.value.error = lastError.value
        break
      case 'done': {
        const finished = {
          taskId: d.task_id,
          status: taskState.value?.status || 'success',
          error: taskState.value?.error || ''
        }
        resetRound()
        if (doneHandler) doneHandler(finished)
        break
      }
      default:
        break
    }
  }

  function send(content) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'chat', content }))
      return true
    }
    return false
  }

  function cancel(taskId) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'cancel', task_id: taskId }))
    }
  }

  return {
    connected,
    taskState,
    streamingText,
    toolEvents,
    lastError,
    connect,
    disconnect,
    send,
    cancel,
    setDoneHandler
  }
})
