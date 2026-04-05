import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Upload, Button, Slider, Tag, message, Spin, Modal } from 'antd'
import {
  InboxOutlined, PlayCircleOutlined, ReloadOutlined,
  ClockCircleOutlined, EnvironmentOutlined, UserOutlined,
  PauseCircleOutlined
} from '@ant-design/icons'
import { frameUrl, searchTrajectory } from '../api.js'

const { Dragger } = Upload

// ── 预设摄像头坐标（归一化 0~1，可按实际校园地图调整）──
const LOCATION_COORDS = {
  '测试摄像头-1号位': { x: 0.50, y: 0.45 },
  '图书馆门口':       { x: 0.28, y: 0.22 },
  '食堂入口':         { x: 0.62, y: 0.38 },
  '教学楼A':          { x: 0.20, y: 0.55 },
  '教学楼B':          { x: 0.45, y: 0.60 },
  '操场':             { x: 0.75, y: 0.28 },
  '宿舍楼':           { x: 0.80, y: 0.65 },
  '校门口':           { x: 0.50, y: 0.85 },
  '行政楼':           { x: 0.35, y: 0.38 },
}

function getCoord(location) {
  if (LOCATION_COORDS[location]) return LOCATION_COORDS[location]
  // 未知位置：基于字符串hash生成稳定坐标
  let h = 0
  for (let c of location) h = (h * 31 + c.charCodeAt(0)) & 0xffff
  return { x: 0.15 + (h % 700) / 1000, y: 0.15 + ((h >> 4) % 700) / 1000 }
}

export default function Trajectory() {
  const [file, setFile]           = useState(null)
  const [preview, setPreview]     = useState(null)
  const [threshold, setThreshold] = useState(0.20)
  const [loading, setLoading]     = useState(false)
  const [result, setResult]       = useState(null)      // API 返回数据
  const [animStep, setAnimStep]   = useState(0)         // 当前动画到第几个节点
  const [playing, setPlaying]     = useState(false)
  const [enlarged, setEnlarged]   = useState(null)

  const canvasRef  = useRef(null)
  const timerRef   = useRef(null)
  const animRef    = useRef({ step: 0, progress: 0 })  // 箭头绘制进度

  // ── 搜索 ──
  const handleSearch = async () => {
    if (!file) return message.warning('请先上传人物图片')
    setLoading(true)
    setResult(null)
    setAnimStep(0)
    setPlaying(false)
    clearInterval(timerRef.current)

    try {
      const { data } = await searchTrajectory(file, threshold, 100)

      if (!data.success) {
        message.error(data.error || '搜索失败')
        return
      }
      if (data.total_appearances === 0) {
        message.info(data.message || '未找到该人物的轨迹')
        setResult(data)
        return
      }
      setResult(data)
      message.success(`找到 ${data.total_appearances} 次出现记录，共 ${data.location_count} 个位置节点`)
    } catch (e) {
      message.error(`搜索失败: ${e?.response?.data?.error || e.message}`)
    } finally {
      setLoading(false)
    }
  }

  // ── 播放动画 ──
  const startAnimation = useCallback(() => {
    if (!result?.location_nodes?.length) return
    setAnimStep(0)
    animRef.current = { step: 0, progress: 0 }
    setPlaying(true)
  }, [result])

  const stopAnimation = () => {
    setPlaying(false)
    clearInterval(timerRef.current)
  }

  // 动画帧驱动
  useEffect(() => {
    if (!playing || !result?.location_nodes?.length) return
    const nodes = result.location_nodes
    const ARROW_FRAMES = 40   // 每段箭头动画帧数
    const PAUSE_FRAMES = 15   // 到达节点后停顿帧数
    let frame = 0

    timerRef.current = setInterval(() => {
      frame++
      const totalFrames = (nodes.length - 1) * (ARROW_FRAMES + PAUSE_FRAMES) + PAUSE_FRAMES
      if (frame > totalFrames) {
        clearInterval(timerRef.current)
        setPlaying(false)
        setAnimStep(nodes.length - 1)
        animRef.current = { step: nodes.length - 1, progress: 1 }
        drawCanvas(result.location_nodes, nodes.length - 1, 1)
        return
      }
      const segLen = ARROW_FRAMES + PAUSE_FRAMES
      const seg    = Math.min(Math.floor(frame / segLen), nodes.length - 2)
      const segF   = frame % segLen
      const prog   = Math.min(segF / ARROW_FRAMES, 1)
      animRef.current = { step: seg, progress: prog }
      setAnimStep(seg)
      drawCanvas(result.location_nodes, seg, prog)
    }, 30)   // ~33fps

    return () => clearInterval(timerRef.current)
  }, [playing])

  // 初始绘制（结果变化或尺寸变化）
  useEffect(() => {
    if (result?.location_nodes?.length) {
      drawCanvas(result.location_nodes, -1, 0)
    }
  }, [result])

  // ── Canvas 绘制 ──
  const drawCanvas = (nodes, currentSeg, progress) => {
    const canvas = canvasRef.current
    if (!canvas || !nodes?.length) return
    const W = canvas.width
    const H = canvas.height
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, W, H)

    // 背景网格
    ctx.strokeStyle = '#1e2d45'
    ctx.lineWidth = 1
    for (let x = 0; x <= W; x += 60) { ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,H); ctx.stroke() }
    for (let y = 0; y <= H; y += 60) { ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke() }

    // 所有摄像头位置标签（背景装饰）
    Object.entries(LOCATION_COORDS).forEach(([name, coord]) => {
      const lx = coord.x * W, ly = coord.y * H
      const isActive = nodes.some(n => n.camera_location === name)
      ctx.fillStyle = isActive ? '#1a2a3a' : '#0f1820'
      ctx.strokeStyle = isActive ? '#2a4060' : '#1e2d45'
      ctx.lineWidth = 1
      ctx.beginPath(); ctx.roundRect(lx - 36, ly - 13, 72, 26, 4); ctx.fill(); ctx.stroke()
      ctx.fillStyle = isActive ? '#5588aa' : '#2a3a4a'
      ctx.font = '11px IBM Plex Mono, monospace'
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
      ctx.fillText(name.length > 7 ? name.slice(0, 7) + '…' : name, lx, ly)
    })

    if (!nodes.length) return

    const pts = nodes.map(n => {
      const coord = getCoord(n.camera_location)
      return { px: coord.x * W, py: coord.y * H, ...n }
    })

    // 已完成的路径段（实线）
    const completedSegs = currentSeg < 0 ? 0 : currentSeg
    for (let i = 0; i < completedSegs && i < pts.length - 1; i++) {
      drawArrow(ctx, pts[i].px, pts[i].py, pts[i+1].px, pts[i+1].py, '#00d4ff', 1, true)
    }

    // 当前正在绘制的箭头（动画中）
    if (currentSeg >= 0 && currentSeg < pts.length - 1 && progress < 1) {
      const a = pts[currentSeg], b = pts[currentSeg + 1]
      const tx = a.px + (b.px - a.px) * easeInOut(progress)
      const ty = a.py + (b.py - a.py) * easeInOut(progress)
      drawArrow(ctx, a.px, a.py, tx, ty, '#00d4ff', easeInOut(progress), false)

      // 动态箭头头部发光
      ctx.beginPath()
      ctx.arc(tx, ty, 6, 0, Math.PI * 2)
      ctx.fillStyle = '#00d4ff'
      ctx.shadowBlur = 16; ctx.shadowColor = '#00d4ff'
      ctx.fill()
      ctx.shadowBlur = 0
    }

    // 绘制节点
    const visibleNodes = currentSeg < 0 ? 0
      : currentSeg >= pts.length - 1 ? pts.length
      : currentSeg + 1
    pts.forEach((p, i) => {
      if (i > visibleNodes) return
      const isFirst = i === 0
      const isLast  = i === pts.length - 1 && currentSeg >= pts.length - 1
      const color   = isFirst ? '#00e5a0' : isLast ? '#ff6b6b' : '#00d4ff'

      // 光晕
      const grd = ctx.createRadialGradient(p.px, p.py, 0, p.px, p.py, 22)
      grd.addColorStop(0, color + '44')
      grd.addColorStop(1, 'transparent')
      ctx.beginPath(); ctx.arc(p.px, p.py, 22, 0, Math.PI * 2)
      ctx.fillStyle = grd; ctx.fill()

      // 外圆
      ctx.beginPath(); ctx.arc(p.px, p.py, 14, 0, Math.PI * 2)
      ctx.strokeStyle = color; ctx.lineWidth = 2
      ctx.fillStyle = '#080c14'; ctx.fill(); ctx.stroke()

      // 内圆
      ctx.beginPath(); ctx.arc(p.px, p.py, 7, 0, Math.PI * 2)
      ctx.fillStyle = color; ctx.fill()

      // 序号
      ctx.fillStyle = '#080c14'
      ctx.font = 'bold 9px sans-serif'
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
      ctx.fillText(p.step, p.px, p.py)

      // 位置名标签
      const label = p.camera_location.length > 8 ? p.camera_location.slice(0,8)+'…' : p.camera_location
      ctx.fillStyle = color
      ctx.font = 'bold 12px Noto Sans SC, sans-serif'
      ctx.textAlign = 'center'
      const offsetY = p.py > H * 0.8 ? -30 : 26
      ctx.fillText(label, p.px, p.py + offsetY)

      // 时间标签
      const fmtT = s => `${String(Math.floor(s/60)).padStart(2,'0')}:${String(Math.floor(s%60)).padStart(2,'0')}`
      ctx.fillStyle = '#8899b0'
      ctx.font = '10px IBM Plex Mono, monospace'
      ctx.fillText(fmtT(p.first_seen), p.px, p.py + offsetY + 16)
    })
  }

  // 画带箭头的线段
  const drawArrow = (ctx, x1, y1, x2, y2, color, alpha, withHead) => {
    const angle = Math.atan2(y2 - y1, x2 - x1)
    const headLen = 12

    ctx.globalAlpha = alpha
    ctx.strokeStyle = color
    ctx.lineWidth = 2.5
    ctx.shadowBlur = 8; ctx.shadowColor = color + '88'

    // 线段（不画到终点，留给箭头）
    const endX = withHead ? x2 - Math.cos(angle) * headLen * 0.5 : x2
    const endY = withHead ? y2 - Math.sin(angle) * headLen * 0.5 : y2
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(endX, endY); ctx.stroke()

    // 箭头头部
    if (withHead) {
      ctx.fillStyle = color
      ctx.beginPath()
      ctx.moveTo(x2, y2)
      ctx.lineTo(x2 - headLen * Math.cos(angle - Math.PI / 6), y2 - headLen * Math.sin(angle - Math.PI / 6))
      ctx.lineTo(x2 - headLen * Math.cos(angle + Math.PI / 6), y2 - headLen * Math.sin(angle + Math.PI / 6))
      ctx.closePath(); ctx.fill()
    }
    ctx.shadowBlur = 0; ctx.globalAlpha = 1
  }

  const easeInOut = t => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t

  const fmtTime = sec => {
    const m = String(Math.floor(sec / 60)).padStart(2, '0')
    const s = String(Math.floor(sec % 60)).padStart(2, '0')
    return `${m}:${s}`
  }

  const nodes = result?.location_nodes || []

  return (
    <div style={{ padding: 24, height: '100%', display: 'flex', flexDirection: 'column', gap: 16, overflow: 'hidden' }}>

      {/* 标题 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <div>
          <h2 style={{ color: 'var(--text-1)', fontSize: 20, fontWeight: 700, marginBottom: 2 }}>时空轨迹追踪</h2>
          <p style={{ color: 'var(--text-3)', fontSize: 12, fontFamily: 'var(--mono)' }}>
            PERSON RE-ID TRAJECTORY · CLIP + FAISS
          </p>
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', gap: 16, overflow: 'hidden', minHeight: 0 }}>

        {/* 左侧：上传 + 控制 */}
        <div style={{ width: 260, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 12, overflow: 'auto' }}>

          {/* 上传区 */}
          <div className="card" style={{ padding: 16 }}>
            <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--mono)', textTransform: 'uppercase', marginBottom: 12 }}>
              上传追踪目标
            </div>
            {preview ? (
              <div>
                <img
                  src={preview} alt="目标"
                  style={{ width: '100%', borderRadius: 8, marginBottom: 10, maxHeight: 180, objectFit: 'contain', background: 'var(--bg-base)' }}
                />
                <Button block onClick={() => { setFile(null); setPreview(null); setResult(null) }}
                  style={{ borderColor: 'var(--border)', color: 'var(--text-2)', marginBottom: 8 }}>
                  重新选择
                </Button>
              </div>
            ) : (
              <Dragger
                accept=".jpg,.jpeg,.png,.bmp,.webp"
                beforeUpload={() => false}
                onChange={info => {
                  const f = info.file.originFileObj || info.file
                  if (f) { setFile(f); setPreview(URL.createObjectURL(f)); setResult(null) }
                  return false
                }}
                showUploadList={false}
                style={{ marginBottom: 0 }}
              >
                <div style={{ padding: '20px 8px', textAlign: 'center' }}>
                  <InboxOutlined style={{ fontSize: 32, color: 'var(--accent)', marginBottom: 8 }} />
                  <div style={{ color: 'var(--text-2)', fontSize: 12 }}>上传人物图片</div>
                  <div style={{ color: 'var(--text-3)', fontSize: 11, marginTop: 4 }}>JPG / PNG / BMP</div>
                </div>
              </Dragger>
            )}

            {/* 阈值 */}
            <div style={{ marginTop: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: 'var(--text-3)' }}>相似度阈值</span>
                <span style={{ fontSize: 12, color: 'var(--accent)', fontFamily: 'var(--mono)' }}>
                  {(threshold * 100).toFixed(0)}%
                </span>
              </div>
              <Slider
                min={5} max={60} value={Math.round(threshold * 100)}
                onChange={v => setThreshold(v / 100)}
                trackStyle={{ background: 'var(--accent)' }}
                handleStyle={{ borderColor: 'var(--accent)' }}
              />
              <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 4 }}>
                阈值越低，找到的匹配越多；越高则越精准
              </div>
            </div>

            <Button
              type="primary" block loading={loading}
              icon={<UserOutlined />}
              onClick={handleSearch}
              style={{ marginTop: 14 }}
              disabled={!file}
            >
              开始追踪
            </Button>
          </div>

          {/* 动画控制 */}
          {nodes.length > 0 && (
            <div className="card" style={{ padding: 16 }}>
              <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--mono)', textTransform: 'uppercase', marginBottom: 12 }}>
                轨迹动画
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                {!playing ? (
                  <Button
                    type="primary" block icon={<PlayCircleOutlined />}
                    onClick={startAnimation}
                  >
                    播放动画
                  </Button>
                ) : (
                  <Button block icon={<PauseCircleOutlined />} onClick={stopAnimation}
                    style={{ borderColor: 'var(--accent)', color: 'var(--accent)' }}>
                    暂停
                  </Button>
                )}
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => { stopAnimation(); drawCanvas(nodes, -1, 0); setAnimStep(0) }}
                  style={{ borderColor: 'var(--border)', color: 'var(--text-2)' }}
                />
              </div>
              <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text-3)' }}>
                已到达：<span style={{ color: 'var(--accent)', fontFamily: 'var(--mono)' }}>
                  {playing || animStep > 0 ? `${Math.min(animStep + 1, nodes.length)}` : '0'} / {nodes.length}
                </span> 个节点
              </div>
            </div>
          )}

          {/* 统计 */}
          {result && result.total_appearances > 0 && (
            <div className="card" style={{ padding: 16 }}>
              <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--mono)', textTransform: 'uppercase', marginBottom: 10 }}>
                追踪结果
              </div>
              {[
                ['总出现次数', result.total_appearances],
                ['经过位置数', result.location_count],
              ].map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ color: 'var(--text-3)', fontSize: 12 }}>{k}</span>
                  <span style={{ color: 'var(--accent)', fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 700 }}>{v}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 中间：轨迹图 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
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
              width={900} height={520}
              style={{ width: '100%', height: '100%', display: 'block' }}
            />

            {/* 加载中 */}
            {loading && (
              <div style={{
                position: 'absolute', inset: 0, display: 'flex',
                alignItems: 'center', justifyContent: 'center',
                background: 'rgba(8,12,20,.7)', flexDirection: 'column', gap: 12,
              }}>
                <Spin size="large" />
                <div style={{ color: 'var(--text-2)', fontFamily: 'var(--mono)', fontSize: 13 }}>
                  正在检索轨迹...
                </div>
              </div>
            )}

            {/* 空状态 */}
            {!loading && !result && (
              <div style={{
                position: 'absolute', inset: 0, display: 'flex',
                flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                gap: 12, color: 'var(--text-3)',
              }}>
                <EnvironmentOutlined style={{ fontSize: 48 }} />
                <div style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>上传人物图片后点击「开始追踪」</div>
                <div style={{ fontSize: 12, maxWidth: 300, textAlign: 'center', lineHeight: 1.7 }}>
                  系统将在所有已处理的视频中搜索该人物，并在地图上以动画形式展示其运动轨迹
                </div>
              </div>
            )}

            {/* 未找到 */}
            {!loading && result && result.total_appearances === 0 && (
              <div style={{
                position: 'absolute', inset: 0, display: 'flex',
                flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                gap: 12, color: 'var(--text-3)',
              }}>
                <UserOutlined style={{ fontSize: 48 }} />
                <div style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>未找到该人物</div>
                <div style={{ fontSize: 12, color: 'var(--yellow)' }}>
                  建议降低相似度阈值后重试
                </div>
              </div>
            )}

            {/* 图例 */}
            {nodes.length > 0 && (
              <div style={{
                position: 'absolute', top: 12, right: 12,
                background: 'rgba(8,12,20,.85)',
                border: '1px solid var(--border)',
                borderRadius: 6, padding: '8px 12px',
                display: 'flex', flexDirection: 'column', gap: 6,
              }}>
                {[
                  { color: '#00e5a0', label: '起点' },
                  { color: '#00d4ff', label: '途经' },
                  { color: '#ff6b6b', label: '终点' },
                ].map(({ color, label }) => (
                  <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: color }} />
                    <span style={{ fontSize: 11, color: 'var(--text-2)' }}>{label}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 右侧：时间线 */}
        <div style={{ width: 220, flexShrink: 0, overflow: 'auto' }}>
          <div className="card" style={{ padding: 16, minHeight: '100%' }}>
            <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--mono)', textTransform: 'uppercase', marginBottom: 14 }}>
              时间线 {nodes.length > 0 && `(${nodes.length} 节点)`}
            </div>

            {nodes.length === 0 ? (
              <div style={{ color: 'var(--text-3)', fontSize: 12 }}>追踪完成后显示</div>
            ) : (
              <div style={{ position: 'relative' }}>
                {/* 连接线 */}
                <div style={{
                  position: 'absolute', left: 7, top: 18, bottom: 18,
                  width: 1, background: 'var(--border)',
                }} />
                {nodes.map((node, i) => {
                  const isVisible = !playing ? true : i <= animStep
                  const isFirst = i === 0
                  const isLast  = i === nodes.length - 1
                  const color   = isFirst ? '#00e5a0' : isLast ? '#ff6b6b' : '#00d4ff'
                  return (
                    <div
                      key={i}
                      style={{
                        display: 'flex', gap: 10, marginBottom: 18,
                        position: 'relative', zIndex: 1,
                        opacity: isVisible ? 1 : 0.25,
                        transition: 'opacity .3s',
                      }}
                    >
                      {/* 节点圆点 */}
                      <div style={{
                        width: 16, height: 16, borderRadius: '50%',
                        background: color, border: '2px solid var(--bg-card)',
                        flexShrink: 0, marginTop: 2,
                        boxShadow: isVisible ? `0 0 8px ${color}88` : 'none',
                        transition: 'box-shadow .3s',
                      }}>
                        <div style={{
                          width: '100%', height: '100%', borderRadius: '50%',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 8, fontWeight: 700, color: '#080c14',
                        }}>{node.step}</div>
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--text-1)', marginBottom: 2 }}>
                          {node.camera_location}
                        </div>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--accent)', marginBottom: 2 }}>
                          <ClockCircleOutlined style={{ marginRight: 3 }} />
                          {fmtTime(node.first_seen)}
                          {node.last_seen > node.first_seen && ` ~ ${fmtTime(node.last_seen)}`}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>
                          出现 {node.appearances} 次 · {(node.score * 100).toFixed(1)}% 相似
                        </div>
                        {/* 关键帧缩略图 */}
                        <img
                          src={frameUrl(node.frame_path)}
                          alt=""
                          onClick={() => setEnlarged({ src: frameUrl(node.frame_path), node })}
                          style={{
                            width: '100%', height: 56, objectFit: 'cover',
                            borderRadius: 4, cursor: 'pointer',
                            border: `1px solid ${isVisible ? color + '66' : 'var(--border)'}`,
                            transition: 'border-color .3s',
                          }}
                          onError={e => e.target.style.display = 'none'}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 放大预览 */}
      <Modal
        open={!!enlarged}
        onCancel={() => setEnlarged(null)}
        footer={null}
        width={720}
        title={enlarged && (
          <span style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--accent)' }}>
            {enlarged.node.camera_location} · {fmtTime(enlarged.node.first_seen)} · {(enlarged.node.score * 100).toFixed(1)}% 相似
          </span>
        )}
      >
        {enlarged && <img src={enlarged.src} alt="预览" style={{ width: '100%', borderRadius: 6 }} />}
      </Modal>
    </div>
  )
}
