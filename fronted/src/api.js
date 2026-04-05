import axios from 'axios'

const BASE = 'http://localhost:5000'

const api = axios.create({ baseURL: BASE, timeout: 60000 })

// ── 请求拦截器：自动附加 JWT token ──
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers['Authorization'] = `Bearer ${token}`
  return config
})

// ── 响应拦截器：token 过期自动跳转登录 ──
api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ── 认证 ──
export const login         = (username, password) =>
  api.post('/api/auth/login', { username, password })
export const logout        = () => api.post('/api/auth/logout')
export const getMe         = () => api.get('/api/auth/me')
export const resetPassword = (answer1, answer2, new_password) =>
  api.post('/api/auth/reset_password', { answer1, answer2, new_password })

// ── 用户管理（超管） ──
export const getUsers    = ()                      => api.get('/api/auth/users')
export const createUser  = (username, password)    => api.post('/api/auth/users', { username, password })
export const updateUser  = (id, data)              => api.put(`/api/auth/users/${id}`, data)
export const deleteUser  = (id)                    => api.delete(`/api/auth/users/${id}`)

// ── 搜索 ──
export const searchByText  = (query, topK = 10) =>
  api.post('/api/search/text', { query, top_k: topK })
export const searchByImage = (file, topK = 10) => {
  const fd = new FormData()
  fd.append('image', file)
  fd.append('top_k', topK)
  return api.post('/api/search/image', fd)
}
export const searchTrajectory = (file, threshold = 0.20, topK = 100) => {
  const fd = new FormData()
  fd.append('image', file)
  fd.append('threshold', threshold)
  fd.append('top_k', topK)
  return api.post('/api/search/trajectory', fd)
}

// ── 监控 ──
export const getVideoSources  = () => api.get('/api/monitor/sources')
export const setVideoSource   = (type, source) =>
  api.post('/api/monitor/set_source', { type, source })
export const getMonitorStatus = () => api.get('/api/monitor/status')
export const stopMonitor      = () => api.post('/api/monitor/stop')
export const streamUrl        = `${BASE}/api/monitor/stream`

// ── 数据管理 ──
export const getVideos    = () => api.get('/api/data/videos')
export const getVideo     = (id) => api.get(`/api/data/videos/${id}`)
export const deleteVideo  = (id) => api.delete(`/api/data/videos/${id}`)
export const uploadVideo  = (file, cameraId, cameraLocation, interval) => {
  const fd = new FormData()
  fd.append('video', file)
  fd.append('camera_id', cameraId)
  fd.append('camera_location', cameraLocation)
  fd.append('interval', interval)
  return api.post('/api/data/upload', fd)
}
export const rebuildIndex = () => api.post('/api/data/rebuild_index')

// ── 搜索历史 ──
export const getHistory    = (params = {}) => api.get('/api/history/', { params })
export const deleteHistory = (id)          => api.delete(`/api/history/${id}`)
export const clearHistory  = (type)        => api.delete('/api/history/', { params: type ? { type } : {} })

// ── 帧图片 / 视频流 URL ──
export const frameUrl    = (path) =>
  `${BASE}/api/data/frame?path=${encodeURIComponent(path)}`
export const videoFileUrl = (videoId) =>
  `${BASE}/api/data/video_file/${videoId}`

export default api
