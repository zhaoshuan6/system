import axios from 'axios'

const BASE = 'http://localhost:5000'
const api = axios.create({ baseURL: BASE, timeout: 60000 })

// 搜索
export const searchByText  = (query, topK = 10) =>
  api.post('/api/search/text', { query, top_k: topK })

export const searchByImage = (file, topK = 10) => {
  const fd = new FormData()
  fd.append('image', file)
  fd.append('top_k', topK)
  return api.post('/api/search/image', fd)
}

// 监控
export const getVideoSources  = () => api.get('/api/monitor/sources')
export const setVideoSource   = (type, source) =>
  api.post('/api/monitor/set_source', { type, source })
export const getMonitorStatus = () => api.get('/api/monitor/status')
export const stopMonitor      = () => api.post('/api/monitor/stop')
export const streamUrl        = `${BASE}/api/monitor/stream`

// 数据管理
export const getVideos   = () => api.get('/api/data/videos')
export const getVideo    = (id) => api.get(`/api/data/videos/${id}`)
export const deleteVideo = (id) => api.delete(`/api/data/videos/${id}`)
export const uploadVideo = (file, cameraId, cameraLocation, interval) => {
  const fd = new FormData()
  fd.append('video', file)
  fd.append('camera_id', cameraId)
  fd.append('camera_location', cameraLocation)
  fd.append('interval', interval)
  return api.post('/api/data/upload', fd)
}
export const rebuildIndex = () => api.post('/api/data/rebuild_index')

// 关键帧图片 URL（直接作为 <img src> 使用）
export const frameUrl = (path) =>
  `${BASE}/api/data/frame?path=${encodeURIComponent(path)}`

// 视频文件 URL（支持 Range，作为 <video src> 使用，有进度条）
export const videoFileUrl = (videoId) =>
  `${BASE}/api/data/video_file/${videoId}`

export default api

// 人物轨迹追踪
export const searchTrajectory = (file, threshold = 0.20, topK = 100) => {
  const fd = new FormData()
  fd.append('image', file)
  fd.append('threshold', threshold)
  fd.append('top_k', topK)
  return api.post('/api/search/trajectory', fd)
}
