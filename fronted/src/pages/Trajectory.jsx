import React, { useState, useEffect, useRef } from 'react'
import { Select, Button, Tag, message, Empty } from 'antd'
import { EnvironmentOutlined, ClockCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import { getVideos } from '../api.js'

export default function Trajectory() {
  const [videos, setVideos]         = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [trajData, setTrajData]     = useState([])
  const canvasRef = useRef(null)

  useEffect(() => { loadVideos() }, [])
  useEffect(() => { if (trajData.length > 0) drawCanvas() }, [trajData])

  const loadVideos = async () => {
    try {
      const { data } = await getVideos()
      setVideos(data.videos || [])
    } catch { message.error('获取视频列表失败') }
  }

  const handleSelect = async (videoId) => {
    setSelectedId(videoId)
    const video = videos.find(v => v.video_id === videoId)
    if (!video) return

    // 根据 video 数据生成轨迹点（基于关键帧时间）
    // 实际项目中这里应该调用后端接口获取真实轨迹
    const points = generateTrajectoryPoints(video)
    setTrajData(points)
  }

  const generateTrajectoryPoints = (video) => {
    // 模拟轨迹点：基于视频时长均匀分布
    const count = video.frame_count || 5
    const duration = video.duration || 100
    const location = video.camera_location || '未知位置'

    // 预设校园地点坐标（归一化 0-1）
    const locationMap = {
      '图书馆门口':   { x: 0.3, y: 0.25 },
      '食堂入口':    { x: 0.6, y: 0.4  },
      '教学楼A':     { x: 0.2, y: 0.55 },
      '教学楼B':     { x: 0.45, y: 0.6 },
      '操场':       { x: 0.75, y: 0.3  },
      '宿舍楼':      { x: 0.8, y: 0.65 },
      '校门口':      { x: 0.5, y: 0.85 },
      '测试摄像头-1号位': { x: 0.5, y: 0.5 },
    }

    const base = locationMap[location] || { x: 0.5, y: 0.5 }

    return Array.from({ length: count }, (_, i) => ({
      x: base.x + (Math.random() - 0.5) * 0.08,
      y: base.y + (Math.random() - 0.5) * 0.08,
      time: (i / Math.max(count - 1, 1)) * duration,
      location,
      frame_index: i,
    }))
  }

  const drawCanvas = () => {
    const canvas = canvasRef.current
    if (!canvas || trajData.length === 0) return
    const ctx = canvas.getContext('2d')
    const W = canvas.width, H = canvas.height

    ctx.clearRect(0, 0, W, H)

    // 背景网格
    ctx.strokeStyle = '#1e2d45'
    ctx.lineWidth = 1
    for (let x = 0; x < W; x += 60) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke()
    }
    for (let y = 0; y < H; y += 60) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke()
    }

    // 绘制地点标签（背景装饰）
    const locations = [
      { label: '图书馆', x: 0.3, y: 0.25 },
      { label: '食堂',   x: 0.6, y: 0.4  },
      { label: '教学楼A', x: 0.2, y: 0.55 },
      { label: '教学楼B', x: 0.45, y: 0.6 },
      { label: '操场',   x: 0.75, y: 0.3  },
      { label: '宿舍楼', x: 0.8, y: 0.65  },
      { label: '校门',   x: 0.5, y: 0.85  },
    ]
    locations.forEach(loc => {
      const lx = loc.x * W, ly = loc.y * H
      ctx.fillStyle = '#1a2236'
      ctx.strokeStyle = '#1e2d45'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.roundRect(lx - 30, ly - 12, 60, 24, 4)
      ctx.fill(); ctx.stroke()
      ctx.fillStyle = '#4a5c72'
      ctx.font = '11px IBM Plex Mono, monospace'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(loc.label, lx, ly)
    })

    if (trajData.length === 0) return

    const pts = trajData.map(p => ({ px: p.x * W, py: p.y * H, ...p }))

    // 绘制轨迹线
    if (pts.length > 1) {
      ctx.beginPath()
      ctx.moveTo(pts[0].px, pts[0].py)
      for (let i = 1; i < pts.length; i++) {
        // 贝塞尔曲线让轨迹更自然
        const mx = (pts[i - 1].px + pts[i].px) / 2
        const my = (pts[i - 1].py + pts[i].py) / 2
        ctx.quadraticCurveTo(pts[i - 1].px, pts[i - 1].py, mx, my)
      }
      ctx.lineTo(pts[pts.length - 1].px, pts[pts.length - 1].py)
      ctx.strokeStyle = '#00d4ff'
      ctx.lineWidth = 2
      ctx.setLineDash([6, 3])
      ctx.stroke()
      ctx.setLineDash([])

      // 轨迹发光效果
      ctx.beginPath()
      ctx.moveTo(pts[0].px, pts[0].py)
      for (let i = 1; i < pts.length; i++) {
        const mx = (pts[i - 1].px + pts[i].px) / 2
        const my = (pts[i - 1].py + pts[i].py) / 2
        ctx.quadraticCurveTo(pts[i - 1].px, pts[i - 1].py, mx, my)
      }
      ctx.strokeStyle = '#00d4ff22'
      ctx.lineWidth = 8
      ctx.stroke()
    }

    // 绘制时间点
    pts.forEach((p, i) => {
      const isFirst = i === 0, isLast = i === pts.length - 1

      // 外圈光晕
      const grd = ctx.createRadialGradient(p.px, p.py, 0, p.px, p.py, isFirst || isLast ? 16 : 12)
      grd.addColorStop(0, isFirst ? '#00e5a022' : isLast ? '#ff4d4f22' : '#00d4ff11')
      grd.addColorStop(1, 'transparent')
      ctx.fillStyle = grd
      ctx.beginPath()
      ctx.arc(p.px, p.py, isFirst || isLast ? 16 : 12, 0, Math.PI * 2)
      ctx.fill()

      // 圆点
      ctx.beginPath()
      ctx.arc(p.px, p.py, isFirst || isLast ? 7 : 5, 0, Math.PI * 2)
      ctx.fillStyle = isFirst ? '#00e5a0' : isLast ? '#ff4d4f' : '#00d4ff'
      ctx.fill()
      ctx.strokeStyle = '#080c14'
      ctx.lineWidth = 2
      ctx.stroke()

      // 时间标签
      const fmtT = (s) => `${Math.floor(s/60).toString().padStart(2,'0')}:${Math.floor(s%60).toString().padStart(2,'0')}`
      ctx.fillStyle = '#e8f0fe'
      ctx.font = '10px IBM Plex Mono, monospace'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'bottom'
      ctx.fillText(fmtT(p.time), p.px, p.py - 10)

      // 序号
      ctx.fillStyle = '#080c14'
      ctx.font = 'bold 8px sans-serif'
      ctx.textBaseline = 'middle'
      ctx.fillText(i + 1, p.px, p.py)
    })
  }

  const fmtTime = (sec) => {
    const m = Math.floor(sec / 60).toString().padStart(2, '0')
    const s = Math.floor(sec % 60).toString().padStart(2, '0')
    return `${m}:${s}`
  }

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20, height: '100%', overflow: 'hidden' }}>
      {/* 标题 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <div>
          <h2 style={{ color: 'var(--text-1)', fontSize: 20, fontWeight: 700, marginBottom: 2 }}>时空轨迹图</h2>
          <p style={{ color: 'var(--text-3)', fontSize: 12, fontFamily: 'var(--mono)' }}>
            SPATIOTEMPORAL TRAJECTORY · CAMPUS MAP
          </p>
        </div>
        <Button icon={<ReloadOutlined />} onClick={loadVideos} style={{ borderColor: 'var(--border)', color: 'var(--text-2)' }}>
          刷新
        </Button>
      </div>

      {/* 控制栏 */}
      <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 16, flexShrink: 0 }}>
        <EnvironmentOutlined style={{ color: 'var(--accent)', fontSize: 16 }} />
        <Select
          placeholder="选择视频/摄像头"
          style={{ width: 300 }}
          value={selectedId}
          onChange={handleSelect}
          options={videos.map(v => ({
            value: v.video_id,
            label: `[ID:${v.video_id}] ${v.camera_location || '未知位置'} · ${v.frame_count}帧`
          }))}
        />
        <div style={{ display: 'flex', gap: 16, marginLeft: 'auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#00e5a0' }} />
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>起点</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#00d4ff' }} />
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>途径点</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#ff4d4f' }} />
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>终点</span>
          </div>
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', gap: 16, overflow: 'hidden', minHeight: 0 }}>
        {/* 地图Canvas */}
        <div style={{
          flex: 1,
          background: 'var(--bg-panel)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          overflow: 'hidden',
          position: 'relative',
        }}>
          <canvas
            ref={canvasRef}
            width={800} height={500}
            style={{ width: '100%', height: '100%', display: 'block' }}
          />
          {!selectedId && (
            <div style={{
              position: 'absolute', inset: 0,
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              gap: 12, color: 'var(--text-3)',
            }}>
              <EnvironmentOutlined style={{ fontSize: 48 }} />
              <div style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>请选择视频以查看轨迹</div>
            </div>
          )}
          {/* 坐标系标注 */}
          <div style={{
            position: 'absolute', top: 12, left: 12,
            fontFamily: 'var(--mono)', fontSize: 10,
            color: 'var(--text-3)',
          }}>
            CAMPUS MAP · TRAJECTORY VIEW
          </div>
        </div>

        {/* 右侧时间线 */}
        <div style={{
          width: 220, flexShrink: 0,
          display: 'flex', flexDirection: 'column', gap: 12,
        }}>
          <div className="card" style={{ padding: 16, flex: 1, overflow: 'auto' }}>
            <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--mono)', textTransform: 'uppercase', marginBottom: 14 }}>
              时间线 ({trajData.length} 个节点)
            </div>

            {trajData.length === 0 ? (
              <div style={{ color: 'var(--text-3)', fontSize: 12 }}>请先选择视频</div>
            ) : (
              <div style={{ position: 'relative' }}>
                {/* 连接线 */}
                <div style={{
                  position: 'absolute', left: 7, top: 16, bottom: 16,
                  width: 1, background: 'var(--border)',
                }} />
                {trajData.map((p, i) => (
                  <div key={i} style={{ display: 'flex', gap: 12, marginBottom: 16, position: 'relative' }}>
                    {/* 圆点 */}
                    <div style={{
                      width: 15, height: 15, borderRadius: '50%', flexShrink: 0, marginTop: 2,
                      background: i === 0 ? '#00e5a0' : i === trajData.length - 1 ? '#ff4d4f' : '#00d4ff',
                      border: '2px solid var(--bg-card)',
                      zIndex: 1,
                    }} />
                    <div>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--accent)' }}>
                        <ClockCircleOutlined style={{ marginRight: 4 }} />
                        {fmtTime(p.time)}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-2)', marginTop: 2 }}>
                        <EnvironmentOutlined style={{ marginRight: 4 }} />
                        {p.location}
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>
                        帧 #{p.frame_index + 1}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
