import request from './request'

// 统一解包统一响应包 {code,message,data}，业务失败时 reject 给调用方处理
function unwrap(promise) {
  return promise.then((r) => r.data.data)
}

export const createConversation = (title) =>
  unwrap(request.post('/api/chat/create', { title }))

export const deleteConversations = (conversationIds) =>
  unwrap(request.post('/api/chat/delete', { conversation_ids: conversationIds }))

export const updateConversation = (conversationId, title) =>
  unwrap(request.post('/api/chat/update', { conversation_id: conversationId, title }))

export const listConversations = () => unwrap(request.get('/api/chat/ls'))

export const listMessages = (conversationId) =>
  unwrap(request.get(`/api/chat/ls/${conversationId}`))
