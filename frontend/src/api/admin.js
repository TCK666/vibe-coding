import request from './request'

function unwrap(p) {
  return p.then((r) => r.data.data)
}

export const listConfigs = () => unwrap(request.get('/api/admin/configs'))

export const setConfig = (config_key, config_value) =>
  unwrap(request.post('/api/admin/configs', { config_key, config_value }))

export const reloadConfig = () => unwrap(request.post('/api/admin/reload'))

export const listLogs = (params) => unwrap(request.get('/api/admin/logs', { params }))
