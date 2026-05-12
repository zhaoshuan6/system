import React, { useState, useEffect, useRef } from 'react'
import { Modal, Button, Spin, Tag, message, Divider } from 'antd'
import {
  PictureOutlined, EnvironmentOutlined, ClockCircleOutlined,
  AimOutlined, CheckCircleOutlined,
} from '@ant-design/icons'
import { searchFromFrame, frameUrl } from '../api.js'
import api from '../api.js'

const fmtTime = (sec) => {
  const m = String(Math.floor(sec / 60)).padStart(2, '0')
  const s = String(Math.floor(sec % 60)).padStart(2, '0')
  return `${m}:${s}`
}

/**
 * 帧图片预览 Modal：叠加 bbox、点击选人、"以图搜图" 和 "轨迹追踪" 两个操作按钮
 *
 * Props:
 *   open        – bool
 *   onClose     – () => void
 *   appearance  – { frame_path, bbox: {x,y,w,h}, frame_time, score }
 *   videoInfo   – { video_id, camera_location }（可选，用于标题）
 */
export default function FramePreviewModal({ open, onClose, appearance, videoInfo }) {
  const [imgLoading, setImgLoading] = useState(false)
  const [selected,   setSelected]   = useState(false)
  const [actionLoading, setActionLoading] = useState(null)   // 'image' | 'trajectory' | null
  const [subResults,    setSubResults]    = useState(null)   // 以图搜图结果
  const [trajResults,   setTrajResults]   = useState(null)   // 轨迹结果
  const [subEnlarged,   setSubEnlarged]   = useState(null)   // 子结果放大预览

  const canvasRef   = useRef(null)
  const imgRef      = useRef(null)
  const blobUrlRef  = useRef(null)
  const scaleRef    = useRef(1)
  const hoveredRef  = useRef(false)
  const selectedRef = useRef(false)

  // ── 打开/切换时重置并加载图片 ──────────────────────────────────
  useEffect(() => {
    if (!open || !appearance?.frame_path) return

    setSelected(false)
    setSubResults(null)
    setTrajResults(null)
    setSubEnlarged(null)
    setActionLoading(null)
    hoveredRef.current  = false
    selectedRef.current = false
    imgRef.current      = null
    setImgLoading(true)

    // 通过 axios 以 blob 形式获取（绕开 CORS canvas taint）
    api.get(`/api/data/frame?path=${encodeURIComponent(appearance.frame_path)}`, {
      responseType: 'blob',
    }).then(resp => {
      if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current)
      blobUrlRef.current = URL.createObjectURL(resp.data)
      const img = new Image()
      img.onload = () => {
        imgRef.current = img
        setImgLoading(false)
        initCanvas()
      }
      img.onerror = () => { setImgLoading(false); message.error('图片加载失败') }
      img.src = blobUrlRef.current
    }).catch(() => { setImgLoading(false); message.error('图片请求失败') })

    return () => {
      if (blobUrlRef.current) { URL.revokeObjectURL(blobUrlRef.current); blobUrlRef.current = null }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, appearance?.frame_path])

  // ── 初始化 canvas 尺寸 + 首次绘制 ────────────────────────────
  const initCanvas = () => {
    const canvas = canvasRef.current
    const img    = imgRef.current
    if (!canvas || !img) return
    const MAX_W = 780
    const scale = Math.min(MAX_W / img.naturalWidth, 1)
    scaleRef.current  = scale
    canvas.width  = Math.round(img.naturalWidth  * scale)
    canvas.height = Math.round(img.naturalHeight * scale)
    draw()
  }

  // ── 绘制函数（纯 canvas 操作，通过 ref 读当前状态） ────────────
  const draw = () => {
    const canvas = canvasRef.current
    const img    = imgRef.current
    if (!canvas || !img || !appearance?.bbox) return

    const ctx   = canvas.getContext('2d')
    const scale = scaleRef.current
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

    const { x, y, w, h } = appearance.bbox
    const bx = Math.round(x * scale)
    const by = Math.round(y * scale)
    const bw = Math.round(w * scale)
    const bh = Math.round(h * scale)

    const isSelected = selectedRef.current
    const isHovered  = hoveredRef.current
    const color = isSelected ? '#52c41a' : '#1677ff'

    // 半透明填充
    ctx.fillStyle = color + (isSelected ? '44' : isHovered ? '33' : '1a')
    ctx.fillRect(bx, by, bw, bh)

    // 边框（选中时虚线）
    ctx.strokeStyle = color
    ctx.lineWidth   = isSelected ? 3 : isHovered ? 2.5 : 2
    if (isSelected) ctx.setLineDash([6, 3])
    ctx.strokeRect(bx, by, bw, bh)
    ctx.setLineDash([])

    // 标签
    const label  = isSelected ? '✓ 已选中' : isHovered ? '点击选择' : '匹配目标'
    ctx.font     = 'bold 13px monospace'
    const lw     = ctx.measureText(label).width + 14
    const lh     = 22
    const ly     = by >= lh ? by - lh : by
    ctx.fillStyle = color
    ctx.fillRect(bx, ly, lw, lh)
    ctx.fillStyle    = '#fff'
    ctx.textAlign    = 'left'
    ctx.textBaseline = 'middle'
    ctx.fillText(label, bx + 7, ly + lh / 2)
  }

  // canvas 初始化时机（imgLoading 变 false 后）
  useEffect(() => {
    if (!imgLoading && imgRef.current) {
      requestAnimationFrame(() => { initCanvas() })
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imgLoading])

  // ── bbox 命中检测 ────────────────────────────────────────────
  const isInsideBbox = (e) => {
    const canvas = canvasRef.current
    if (!canvas || !appearance?.bbox) return false
    const rect  = canvas.getBoundingClientRect()
    const mx    = (e.clientX - rect.left) * (canvas.width  / rect.width)
    const my    = (e.clientY - rect.top)  * (canvas.height / rect.height)
    const { x, y, w, h } = appearance.bbox
    const s = scaleRef.current
    return mx >= x * s && mx <= (x + w) * s && my >= y * s && my <= (y + h) * s
  }

  const handleMouseMove = (e) => {
    const inside = isInsideBbox(e)
    if (inside !== hoveredRef.current) {
      hoveredRef.current = inside
      if (canvasRef.current) canvasRef.current.style.cursor = inside ? 'pointer' : 'default'
      draw()
    }
  }

  const handleMouseLeave = () => {
    hoveredRef.current = false
    if (canvasRef.current) canvasRef.current.style.cursor = 'default'
    draw()
  }

  const handleCanvasClick = (e) => {
    if (isInsideBbox(e)) {
      selectedRef.current = true
      setSelected(true)
      draw()
    }
  }

  // ── 操作函数 ─────────────────────────────────────────────────
  const bboxParam = () => {
    const { x, y, w, h } = appearance.bbox
    return `${x},${y},${w},${h}`
  }

  const handleImageSearch = async () => {
    setActionLoading('image')
    setSubResults(null)
    setTrajResults(null)
    try {
      const { data } = await searchFromFrame(appearance.frame_path, bboxParam(), 'image', 10)
      if (!data.success) throw new Error(data.error)
      setSubResults(data.results || [])
      if (!(data.results || []).length) message.info('未找到相似人物')
    } catch (e) {
      message.error(`以图搜图失败: ${e?.response?.data?.error || e.message}`)
    } finally {
      setActionLoading(null)
    }
  }

  const handleTrajectory = async () => {
    setActionLoading('trajectory')
    setSubResults(null)
    setTrajResults(null)
    try {
      const { data } = await searchFromFrame(appearance.frame_path, bboxParam(), 'trajectory', 100, 0.20)
      if (!data.success) throw new Error(data.error)
      if (data.total_appearances === 0) {
        message.info(data.message || '未找到该人物的轨迹')
        setTrajResults({ location_nodes: [], total_appearances: 0 })
      } else {
        setTrajResults(data)
      }
    } catch (e) {
      message.error(`轨迹追踪失败: ${e?.response?.data?.error || e.message}`)
    } finally {
      setActionLoading(null)
    }
  }

  const handleClose = () => {
    setSelected(false)
    setSubResults(null)
    setTrajResults(null)
    setSubEnlarged(null)
    onClose()
  }

  // ── 渲染 ─────────────────────────────────────────────────────
  const nodes = trajResults?.location_nodes || []

  return (
    <>
      <Modal
        open={open}
        onCancel={handleClose}
        footer={null}
        width={880}
        centered
        maskClosable={false}
        keyboard={false}
        styles={{ body: { maxHeight: '80vh', overflowY: 'auto' } }}
        title={appearance && (
          <span style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--accent)' }}>
            {videoInfo?.camera_location && (
              <Tag icon={<EnvironmentOutlined />} color="blue" style={{ marginRight: 8, fontSize: 11 }}>
                {videoInfo.camera_location}
              </Tag>
            )}
            <ClockCircleOutlined style={{ marginRight: 4 }} />
            {fmtTime(appearance.frame_time)}
            &nbsp;·&nbsp;
            相似度 {(appearance.score * 100).toFixed(1)}%
          </span>
        )}
      >
        {/* ── 帧图片 canvas ── */}
        <div style={{ display: 'flex', justifyContent: 'center', position: 'relative', minHeight: 120 }}>
          {imgLoading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
              <Spin size="large" />
            </div>
          ) : (
            <canvas
              ref={canvasRef}
              style={{ maxWidth: '100%', display: 'block', borderRadius: 6 }}
              onMouseMove={handleMouseMove}
              onMouseLeave={handleMouseLeave}
              onClick={handleCanvasClick}
            />
          )}
        </div>

        {/* ── 提示 & 操作按钮 ── */}
        {!imgLoading && (
          <div style={{ marginTop: 10, textAlign: 'center' }}>
            {!selected ? (
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '5px 12px', background: 'var(--bg-base)', borderRadius: 6,
                border: '1px dashed var(--border)',
              }}>
                <AimOutlined style={{ color: 'var(--accent)' }} />
                <span style={{ fontSize: 12, color: 'var(--text-3)' }}>
                  点击图中蓝色框选中目标人物
                </span>
              </div>
            ) : (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12 }}>
                <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />
                <span style={{ fontSize: 12, color: '#52c41a' }}>已选中目标人物</span>
                <Button
                  type="primary"
                  icon={<PictureOutlined />}
                  loading={actionLoading === 'image'}
                  disabled={actionLoading === 'trajectory'}
                  onClick={handleImageSearch}
                >
                  以图搜图
                </Button>
                <Button
                  icon={<EnvironmentOutlined />}
                  loading={actionLoading === 'trajectory'}
                  disabled={actionLoading === 'image'}
                  onClick={handleTrajectory}
                  style={{ borderColor: 'var(--accent)', color: 'var(--accent)' }}
                >
                  轨迹追踪
                </Button>
              </div>
            )}
          </div>
        )}

        {/* ── 以图搜图子结果 ── */}
        {subResults !== null && (
          <>
            <Divider style={{ margin: '16px 0 12px' }}>
              <span style={{ fontSize: 12, color: 'var(--text-3)' }}>
                以图搜图结果
                {subResults.length > 0 && (
                  <span style={{ color: 'var(--accent)', marginLeft: 6 }}>
                    {subResults.length} 个视频
                  </span>
                )}
              </span>
            </Divider>
            {subResults.length === 0 ? (
              <div style={{ textAlign: 'center', color: 'var(--text-3)', fontSize: 13, padding: '12px 0' }}>
                未找到相似人物
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {subResults.map((r, i) => (
                  <div key={r.video_id} className="card" style={{ padding: '10px 14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                      <span style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>#{i + 1}</span>
                      <span style={{ color: 'var(--accent)', fontWeight: 600, fontSize: 13 }}>
                        视频 {r.video_id}
                      </span>
                      <Tag icon={<EnvironmentOutlined />} color="blue" style={{ fontSize: 10 }}>
                        {r.camera_location}
                      </Tag>
                      <span style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--green)' }}>
                        {(r.max_score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))', gap: 6 }}>
                      {(r.appearances || []).slice(0, 6).map((a, j) => (
                        <div
                          key={j}
                          onClick={() => setSubEnlarged({ src: frameUrl(a.frame_path), time: a.frame_time, score: a.score })}
                          style={{
                            position: 'relative', borderRadius: 5, overflow: 'hidden',
                            border: '1px solid var(--border)', cursor: 'pointer',
                          }}
                          onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
                          onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
                        >
                          <img
                            src={frameUrl(a.frame_path)} alt=""
                            style={{ width: '100%', aspectRatio: '16/9', objectFit: 'cover', display: 'block', background: 'var(--bg-base)' }}
                            onError={e => { e.target.style.display = 'none' }}
                          />
                          <div style={{
                            position: 'absolute', bottom: 0, left: 0, right: 0,
                            background: 'linear-gradient(transparent,rgba(0,0,0,.75))',
                            padding: '6px 4px 3px',
                            display: 'flex', justifyContent: 'space-between',
                          }}>
                            <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#fff' }}>
                              {fmtTime(a.frame_time)}
                            </span>
                            <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--green)' }}>
                              {(a.score * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                    {(r.appearances || []).length > 6 && (
                      <div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>
                        共 {r.appearances.length} 次，显示前 6 条
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* ── 轨迹追踪子结果 ── */}
        {trajResults !== null && (
          <>
            <Divider style={{ margin: '16px 0 12px' }}>
              <span style={{ fontSize: 12, color: 'var(--text-3)' }}>
                轨迹追踪结果
                {nodes.length > 0 && (
                  <span style={{ color: 'var(--accent)', marginLeft: 6 }}>
                    {trajResults.total_appearances} 次出现 · {nodes.length} 个位置
                  </span>
                )}
              </span>
            </Divider>
            {nodes.length === 0 ? (
              <div style={{ textAlign: 'center', color: 'var(--text-3)', fontSize: 13, padding: '12px 0' }}>
                未找到该人物的轨迹
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {nodes.map((node, i) => {
                  const isFirst = i === 0
                  const isLast  = i === nodes.length - 1
                  const color   = isFirst ? '#389e0d' : isLast ? '#cf1322' : '#1677ff'
                  return (
                    <div key={i} style={{
                      display: 'flex', gap: 12, alignItems: 'flex-start',
                      padding: '10px 14px', borderRadius: 8,
                      border: `1px solid ${color}44`,
                      background: color + '08',
                    }}>
                      {/* 步骤圆点 */}
                      <div style={{
                        width: 28, height: 28, borderRadius: '50%',
                        background: color + '20', border: `2px solid ${color}`,
                        flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 11, fontWeight: 700, color,
                      }}>
                        {node.step}
                      </div>
                      {/* 信息 */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-1)', marginBottom: 3 }}>
                          {node.camera_location}
                        </div>
                        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 11, color: 'var(--text-3)' }}>
                          <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>
                            <ClockCircleOutlined style={{ marginRight: 3 }} />
                            {fmtTime(node.first_seen)}
                            {node.last_seen > node.first_seen && ` ~ ${fmtTime(node.last_seen)}`}
                          </span>
                          <span>出现 {node.appearances} 次</span>
                          <span style={{ color: 'var(--green)' }}>
                            {(node.score * 100).toFixed(1)}% 相似
                          </span>
                        </div>
                      </div>
                      {/* 关键帧缩略图 */}
                      <img
                        src={frameUrl(node.frame_path)} alt=""
                        onClick={() => setSubEnlarged({ src: frameUrl(node.frame_path), time: node.first_seen, score: node.score })}
                        style={{
                          width: 80, height: 50, objectFit: 'cover', borderRadius: 4,
                          border: `1px solid ${color}44`, cursor: 'pointer', flexShrink: 0,
                        }}
                        onError={e => { e.target.style.display = 'none' }}
                      />
                    </div>
                  )
                })}
              </div>
            )}
          </>
        )}
      </Modal>

      {/* 子结果帧放大预览 */}
      <Modal
        open={!!subEnlarged}
        onCancel={() => setSubEnlarged(null)}
        footer={null} width={760} centered
        title={subEnlarged && (
          <span style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--accent)' }}>
            时间: {fmtTime(subEnlarged.time)} · 相似度: {(subEnlarged.score * 100).toFixed(1)}%
          </span>
        )}
      >
        {subEnlarged && <img src={subEnlarged.src} alt="预览" style={{ width: '100%', borderRadius: 6 }} />}
      </Modal>
    </>
  )
}
