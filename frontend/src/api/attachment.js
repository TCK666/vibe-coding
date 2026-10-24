import request from './request'

function unwrap(promise) {
  return promise.then((r) => r.data.data)
}

export const uploadAttachment = (conversationId, file, onProgress) => {
  const form = new FormData()
  form.append('conversation_id', String(conversationId))
  form.append('file', file)
  return unwrap(
    request.post('/api/attachment/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      }
    })
  )
}

export const listAttachments = (conversationId) =>
  unwrap(request.get('/api/attachment/ls', { params: { conversation_id: conversationId } }))

export const deleteAttachment = (attachmentId) =>
  unwrap(request.post('/api/attachment/delete', { attachment_id: attachmentId }))

// 鉴权下载：axios 带 Bearer 拉二进制，再触发浏览器保存
export async function downloadAttachment(att) {
  const resp = await request.get('/api/attachment/get', {
    params: { attachment_id: att.attachment_id },
    responseType: 'blob'
  })
  const url = URL.createObjectURL(resp.data)
  const a = document.createElement('a')
  a.href = url
  a.download = att.file_name
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
