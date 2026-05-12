import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Upload, Button, Slider, Tag, Modal, message, Empty, Spin } from 'antd'
import {
  InboxOutlined, SearchOutlined, ClockCircleOutlined,
  EnvironmentOutlined, UserOutlined, AimOutlined,
} from '@ant-design/icons'
import { detectPersons, searchByImageKey, searchByImage, frameUrl } from '../api.js'
import FramePreviewModal from '../components/FramePreviewModal.jsx'

const { Dragger } = Upload

// 检测框颜色池（8 种）
const PERSON_COLORS = [
  '#ff4d4f', '#1677ff', '#52c41a', '#fa8c16',
  '#722ed1', '#13c2c2', '#eb2f96', '#fadb14',
]

export default function ImageSearch() {
  const [file, setFile]         = useState(null)
  const [preview, setPreview]   = useState(null)
  const [topK, setTopK]         = useState(10)
  const [loading, setLoading]   = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [results, setResults]   = useState(null)
  const [enlarged, setEnlarged] = useState(null)

  // 检测结果
  const [imageKey, setImageKey]   = useState(null)
  const [persons, setPersons]     = useState([])   // [{bbox,confidence}]

  // 放大预览 Modal
  const [zoomOpen, setZoomOpen]   = useState(false)

  // 小图 Canvas refs
  const canvasRef      = useRef(null)
  const imgObjRef      = useRef(null)
  const scaleRef       = useRef(1)
  const hoveredRef     = useRef(-1)
  const selectedRef    = useRef(-1)
  const personsRef     = useRef([])

  // 放大图 Canvas refs
  const modalCanvasRef  = useRef(null)
  const modalScaleRef   = useRef(1)
  const modalHovRef     = useRef(-1)

  // ── Canvas 绘制 ──────────────────────────────────────────────
  const redrawCanvas = useCallback(() => {
    const canvas = canvasRef.current
    const img    = imgObjRef.current
    if (!canvas || !img) return

    const ctx   = canvas.getContext('2d')
    const scale = scaleRef.current
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

    personsRef.current.forEach((p, i) => {
      const [x1, y1, x2, y2] = p.bbox.map(v => Math.round(v * scale))
      const color      = PERSON_COLORS[i % PERSON_COLORS.length]
      const isHovered  = i === hoveredRef.current
      const isSelected = i === selectedRef.current

      // 半透明填充
      ctx.fillStyle = color + (isHovered ? '55' : isSelected ? '44' : '22')
      ctx.fillRect(x1, y1, x2 - x1, y2 - y1)

      // 边框
      ctx.strokeStyle = color
      ctx.lineWidth   = (isHovered || isSelected) ? 3 : 2
      if (isSelected) ctx.setLineDash([])
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
      ctx.setLineDash([])

      // 标签背景
      const label  = `P${i + 1}  ${(p.confidence * 100).toFixed(0)}%`
      ctx.font     = 'bold 11px monospace'
      const labelW = ctx.measureText(label).width + 10
      const labelH = 18
      const labelY = y1 >= labelH ? y1 - labelH : y1
      ctx.fillStyle = color
      ctx.fillRect(x1, labelY, labelW, labelH)

      // 标签文字
      ctx.fillStyle    = '#ffffff'
      ctx.textAlign    = 'left'
      ctx.textBaseline = 'middle'
      ctx.fillText(label, x1 + 5, labelY + labelH / 2)
    })
  }, [])

  // ── 放大 Canvas 绘制（复用相同绘制逻辑，字体稍大） ─────────────
  const redrawModalCanvas = useCallback(() => {
    const canvas = modalCanvasRef.current
    const img    = imgObjRef.current
    if (!canvas || !img) return
    const ctx   = canvas.getContext('2d')
    const scale = modalScaleRef.current
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

    personsRef.current.forEach((p, i) => {
      const [x1, y1, x2, y2] = p.bbox.map(v => Math.round(v * scale))
      const color      = PERSON_COLORS[i % PERSON_COLORS.length]
      const isHovered  = i === modalHovRef.current
      const isSelected = i === selectedRef.current

      ctx.fillStyle = color + (isHovered ? '55' : isSelected ? '44' : '22')
      ctx.fillRect(x1, y1, x2 - x1, y2 - y1)
      ctx.strokeStyle = color
      ctx.lineWidth   = (isHovered || isSelected) ? 3 : 2
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)

      const label  = `P${i + 1}  ${(p.confidence * 100).toFixed(0)}%`
      ctx.font     = 'bold 13px monospace'
      const labelW = ctx.measureText(label).width + 12
      const labelH = 22
      const labelY = y1 >= labelH ? y1 - labelH : y1
      ctx.fillStyle = color
      ctx.fillRect(x1, labelY, labelW, labelH)
      ctx.fillStyle    = '#ffffff'
      ctx.textAlign    = 'left'
      ctx.textBaseline = 'middle'
      ctx.fillText(label, x1 + 6, labelY + labelH / 2)
    })
  }, [])

  // 放大 Modal 打开时初始化 canvas
  useEffect(() => {
    if (!zoomOpen || !imgObjRef.current) return
    // 等一帧让 Modal 的 canvas DOM 就绪
    requestAnimationFrame(() => {
      const canvas = modalCanvasRef.current
      if (!canvas) return
      const img = imgObjRef.current
      const MAX_W = 780, MAX_H = 560
      const wScale = MAX_W / img.naturalWidth
      const hScale = MAX_H / img.naturalHeight
      const scale  = Math.min(wScale, hScale, 1)   // 不超过原始尺寸
      modalScaleRef.current  = scale
      canvas.width  = Math.round(img.naturalWidth  * scale)
      canvas.height = Math.round(img.naturalHeight * scale)
      modalHovRef.current = -1
      redrawModalCanvas()
    })
  }, [zoomOpen, redrawModalCanvas])

  // ── 加载图片对象 ─────────────────────────────────────────────
  useEffect(() => {
    if (!preview) { imgObjRef.current = null; return }
    const img = new Image()
    img.onload = () => {
      imgObjRef.current = img
      // 如果此时已有 persons，立即初始化 canvas
      if (personsRef.current.length > 0 && canvasRef.current) {
        const scale = canvasRef.current.clientWidth / img.naturalWidth
        scaleRef.current  = scale
        canvasRef.current.width  = canvasRef.current.clientWidth || 248
        canvasRef.current.height = Math.round(img.naturalHeight * scale)
        redrawCanvas()
      }
    }
    img.src = preview
  }, [preview, redrawCanvas])

  // ── persons 更新后初始化 canvas ──────────────────────────────
  useEffect(() => {
    personsRef.current = persons
    if (!persons.length || !imgObjRef.current || !canvasRef.current) return
    const img   = imgObjRef.current
    const cw    = canvasRef.current.clientWidth || 248
    const scale = cw / img.naturalWidth
    scaleRef.current         = scale
    canvasRef.current.width  = cw
    canvasRef.current.height = Math.round(img.naturalHeight * scale)
    hoveredRef.current  = -1
    selectedRef.current = -1
    redrawCanvas()
  }, [persons, redrawCanvas])

  // ── 上传处理：自动触发检测 ───────────────────────────────────
  const handleFileChange = useCallback(async (info) => {
    const f = info.file.originFileObj || info.file
    if (!f) return false

    // 重置状态
    setFile(f)
    setPreview(URL.createObjectURL(f))
    setResults(null)
    setPersons([])
    setImageKey(null)
    personsRef.current  = []
    hoveredRef.current  = -1
    selectedRef.current = -1

    // 自动检测
    setDetecting(true)
    try {
      const { data } = await detectPersons(f)
      if (data.success) {
        setImageKey(data.image_key)
        setPersons(data.persons)
      } else {
        message.warning(data.error || '人物检测失败，可搜索整张图片')
      }
    } catch {
      message.warning('人物检测失败，可搜索整张图片')
    } finally {
      setDetecting(false)
    }
    return false
  }, [])

  // ── Canvas 鼠标事件 ──────────────────────────────────────────
  const getPersonAtPoint = useCallback((e) => {
    const canvas = canvasRef.current
    if (!canvas || !personsRef.current.length) return -1
    const rect  = canvas.getBoundingClientRect()
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    const mx = (e.clientX - rect.left) * scaleX
    const my = (e.clientY - rect.top)  * scaleY
    const ps = personsRef.current
    for (let i = ps.length - 1; i >= 0; i--) {
      const [x1, y1, x2, y2] = ps[i].bbox.map(v => Math.round(v * scaleRef.current))
      if (mx >= x1 && mx <= x2 && my >= y1 && my <= y2) return i
    }
    return -1
  }, [])

  const handleCanvasMouseMove = useCallback((e) => {
    const idx = getPersonAtPoint(e)
    if (idx !== hoveredRef.current) {
      hoveredRef.current = idx
      if (canvasRef.current)
        canvasRef.current.style.cursor = idx >= 0 ? 'pointer' : 'default'
      redrawCanvas()
    }
  }, [getPersonAtPoint, redrawCanvas])

  const handleCanvasMouseLeave = useCallback(() => {
    hoveredRef.current = -1
    if (canvasRef.current) canvasRef.current.style.cursor = 'default'
    redrawCanvas()
  }, [redrawCanvas])

  // 小图点击 → 直接打开放大 Modal
  const handleCanvasClick = useCallback(() => {
    setZoomOpen(true)
  }, [])

  // ── 放大 Modal 内的交互 ──────────────────────────────────────
  const getModalPersonAt = useCallback((e) => {
    const canvas = modalCanvasRef.current
    if (!canvas || !personsRef.current.length) return -1
    const rect  = canvas.getBoundingClientRect()
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    const mx = (e.clientX - rect.left) * scaleX
    const my = (e.clientY - rect.top)  * scaleY
    const ps = personsRef.current
    for (let i = ps.length - 1; i >= 0; i--) {
      const [x1, y1, x2, y2] = ps[i].bbox.map(v => Math.round(v * modalScaleRef.current))
      if (mx >= x1 && mx <= x2 && my >= y1 && my <= y2) return i
    }
    return -1
  }, [])

  const handleModalMouseMove = useCallback((e) => {
    const idx = getModalPersonAt(e)
    if (idx !== modalHovRef.current) {
      modalHovRef.current = idx
      if (modalCanvasRef.current)
        modalCanvasRef.current.style.cursor = idx >= 0 ? 'pointer' : 'default'
      redrawModalCanvas()
    }
  }, [getModalPersonAt, redrawModalCanvas])

  const handleModalMouseLeave = useCallback(() => {
    modalHovRef.current = -1
    if (modalCanvasRef.current) modalCanvasRef.current.style.cursor = 'default'
    redrawModalCanvas()
  }, [redrawModalCanvas])

  const handleModalClick = useCallback(async (e) => {
    const idx = getModalPersonAt(e)
    if (idx < 0) return
    // 同步选中状态到小图
    selectedRef.current = idx
    redrawCanvas()
    redrawModalCanvas()
    setZoomOpen(false)

    const person = personsRef.current[idx]
    setLoading(true)
    setResults(null)
    try {
      const { data } = await searchByImageKey(imageKey, person.bbox, topK)
      setResults(data.results || [])
      if (!(data.results || []).length) message.info('未找到匹配人物')
    } catch (err) {
      message.error(`搜索失败: ${err?.response?.data?.error || err.message}`)
    } finally {
      setLoading(false)
    }
  }, [getModalPersonAt, redrawCanvas, redrawModalCanvas, imageKey, topK])

  // ── 兜底搜索（无人物检测到时） ───────────────────────────────
  const handleFallbackSearch = async () => {
    if (!file) return
    setLoading(true)
    setResults(null)
    try {
      const { data } = await searchByImage(file, topK)
      setResults(data.results || [])
      if (!(data.results || []).length) message.info('未找到匹配人物')
    } catch (e) {
      message.error(`搜索失败: ${e?.response?.data?.error || e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const resetFile = () => {
    setFile(null); setPreview(null); setResults(null)
    setPersons([]); setImageKey(null)
    personsRef.current = []; imgObjRef.current = null
    hoveredRef.current = -1; selectedRef.current = -1
  }

  const fmtTime = (sec) => {
    const m = Math.floor(sec / 60).toString().padStart(2, '0')
    const s = Math.floor(sec % 60).toString().padStart(2, '0')
    return `${m}:${s}`
  }

  // ── 渲染 ─────────────────────────────────────────────────────
  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20, height: '100%' }}>
      <div>
        <h2 style={{ color: 'var(--text-1)', fontSize: 20, fontWeight: 700, marginBottom: 2 }}>以图搜图</h2>
        <p style={{ color: 'var(--text-3)', fontSize: 12, fontFamily: 'var(--mono)' }}>
          IMAGE-TO-VIDEO SEARCH · YOLOV8 + CLIP
        </p>
      </div>

      <div style={{ display: 'flex', gap: 20, flex: 1, overflow: 'hidden' }}>
        {/* ── 左侧面板 ── */}
        <div style={{ width: 280, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* 上传 / 检测区 */}
          <div className="card" style={{ padding: 16 }}>
            <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 12, fontFamily: 'var(--mono)', textTransform: 'uppercase' }}>
              上传查询图片
            </div>

            {/* 未选文件 */}
            {!file && (
              <Dragger
                accept=".jpg,.jpeg,.png,.bmp,.webp"
                beforeUpload={() => false}
                onChange={handleFileChange}
                showUploadList={false}
                style={{ background: 'var(--bg-base)', border: '1px dashed var(--border)', borderRadius: 8 }}
              >
                <div style={{ padding: '20px 10px', textAlign: 'center' }}>
                  <InboxOutlined style={{ fontSize: 36, color: 'var(--accent)', marginBottom: 8 }} />
                  <div style={{ color: 'var(--text-2)', fontSize: 13, marginBottom: 4 }}>点击或拖拽人物图片</div>
                  <div style={{ color: 'var(--text-3)', fontSize: 11 }}>支持 JPG / PNG / BMP</div>
                </div>
              </Dragger>
            )}

            {/* 检测中 */}
            {file && detecting && (
              <div style={{ textAlign: 'center', padding: '28px 0' }}>
                <Spin size="large" />
                <div style={{ marginTop: 12, color: 'var(--text-3)', fontSize: 12 }}>正在检测人物...</div>
              </div>
            )}

            {/* 有人物 → Canvas 交互（点击打开放大） */}
            {file && !detecting && persons.length > 0 && (
              <div>
                <div
                  style={{
                    position: 'relative', borderRadius: 8, overflow: 'hidden',
                    marginBottom: 8, border: '1px solid var(--border)', cursor: 'zoom-in',
                  }}
                  onClick={handleCanvasClick}
                  onMouseMove={handleCanvasMouseMove}
                  onMouseLeave={handleCanvasMouseLeave}
                  title="点击放大选择人物"
                >
                  <canvas
                    ref={canvasRef}
                    style={{ width: '100%', display: 'block', pointerEvents: 'none' }}
                  />
                  {/* 放大提示角标 */}
                  <div style={{
                    position: 'absolute', top: 6, right: 6,
                    background: 'rgba(0,0,0,0.55)', borderRadius: 4,
                    padding: '2px 6px', fontSize: 10, color: '#fff',
                    display: 'flex', alignItems: 'center', gap: 4, pointerEvents: 'none',
                  }}>
                    🔍 点击放大
                  </div>
                </div>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10,
                  padding: '5px 8px', background: 'var(--bg-base)', borderRadius: 6,
                }}>
                  <AimOutlined style={{ color: 'var(--accent)', fontSize: 12 }} />
                  <span style={{ fontSize: 11, color: 'var(--text-3)' }}>
                    检测到&nbsp;
                    <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{persons.length}</span>
                    &nbsp;个人物，点击图片放大后选择查询目标
                  </span>
                </div>
                {/* 颜色图例 */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
                  {persons.map((p, i) => (
                    <Tag
                      key={i}
                      style={{
                        borderColor: PERSON_COLORS[i % PERSON_COLORS.length],
                        color: PERSON_COLORS[i % PERSON_COLORS.length],
                        background: PERSON_COLORS[i % PERSON_COLORS.length] + '18',
                        fontSize: 11, cursor: 'pointer',
                        outline: selectedRef.current === i ? `2px solid ${PERSON_COLORS[i % PERSON_COLORS.length]}` : 'none',
                      }}
                    >
                      P{i + 1} · {(p.confidence * 100).toFixed(0)}%
                    </Tag>
                  ))}
                </div>
                <Button block onClick={resetFile} style={{ borderColor: 'var(--border)', color: 'var(--text-2)' }}>
                  重新选择
                </Button>
              </div>
            )}

            {/* 无人物 → 原图预览 + 兜底搜索 */}
            {file && !detecting && persons.length === 0 && (
              <div>
                <div style={{ position: 'relative', borderRadius: 8, overflow: 'hidden', marginBottom: 8 }}>
                  <img
                    src={preview} alt="查询图片"
                    style={{ width: '100%', display: 'block', maxHeight: 200, objectFit: 'contain', background: 'var(--bg-base)' }}
                  />
                  <Tag color="orange" style={{ position: 'absolute', top: 8, left: 8, fontSize: 10 }}>
                    未检测到人物
                  </Tag>
                </div>
                <Button
                  type="primary" block icon={<SearchOutlined />}
                  loading={loading} onClick={handleFallbackSearch}
                  style={{ marginBottom: 8 }}
                >
                  搜索整张图片
                </Button>
                <Button block onClick={resetFile} style={{ borderColor: 'var(--border)', color: 'var(--text-2)' }}>
                  重新选择
                </Button>
              </div>
            )}
          </div>

          {/* 搜索参数 */}
          <div className="card" style={{ padding: 16 }}>
            <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 12, fontFamily: 'var(--mono)', textTransform: 'uppercase' }}>
              搜索参数
            </div>
            <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-2)', fontSize: 12 }}>返回视频数</span>
              <span style={{ color: 'var(--accent)', fontFamily: 'var(--mono)', fontSize: 12 }}>{topK}</span>
            </div>
            <Slider
              min={1} max={20} value={topK} onChange={setTopK}
              trackStyle={{ background: 'var(--accent)' }}
              handleStyle={{ borderColor: 'var(--accent)' }}
            />
          </div>

          {/* 说明 */}
          <div className="card" style={{ padding: 16, fontSize: 12, color: 'var(--text-3)', lineHeight: 1.8 }}>
            <div style={{ color: 'var(--text-2)', marginBottom: 8 }}>📖 使用说明</div>
            <div>1. 上传包含目标人物的图片</div>
            <div>2. YOLOv8 自动检测并标记所有人物</div>
            <div>3. 点击框内人物选择查询目标</div>
            <div>4. CLIP 提取特征后在数据库中检索</div>
          </div>
        </div>

        {/* ── 右侧结果区 ── */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          {results === null && !loading && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <div style={{ textAlign: 'center', color: 'var(--text-3)' }}>
                <UserOutlined style={{ fontSize: 48, marginBottom: 16 }} />
                <div style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>上传图片后点击人物框进行查询</div>
              </div>
            </div>
          )}

          {loading && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <div style={{ textAlign: 'center' }}>
                <Spin size="large" />
                <div style={{ marginTop: 12, color: 'var(--text-3)', fontFamily: 'var(--mono)', fontSize: 13 }}>
                  正在搜索...
                </div>
              </div>
            </div>
          )}

          {results && results.length === 0 && (
            <Empty description={<span style={{ color: 'var(--text-3)' }}>未找到匹配人物</span>} />
          )}

          {results && results.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ color: 'var(--text-3)', fontSize: 12, fontFamily: 'var(--mono)' }}>
                在 <span style={{ color: 'var(--accent)' }}>{results.length}</span> 个视频中找到该人物
              </div>

              {results.map((r, i) => (
                <div key={r.video_id} className="card fade-in" style={{ animationDelay: `${i * 0.05}s` }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-3)' }}>#{i + 1}</span>
                    <span style={{ color: 'var(--accent)', fontWeight: 600, fontSize: 14 }}>
                      视频 ID: {r.video_id}
                    </span>
                    <Tag icon={<EnvironmentOutlined />} color="blue" style={{ fontSize: 11 }}>
                      {r.camera_location}
                    </Tag>
                    <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ width: 80 }}>
                        <div className="score-bar">
                          <div className="score-bar-fill" style={{ width: `${Math.min(100, Math.round(r.max_score * 100))}%` }} />
                        </div>
                      </div>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--green)', minWidth: 50 }}>
                        {(r.max_score * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 8 }}>
                    {r.appearances.slice(0, 8).map((a, j) => (
                      <div
                        key={j}
                        onClick={() => setEnlarged({ frame_path: a.frame_path, bbox: a.bbox, frame_time: a.frame_time, score: a.score, video_id: r.video_id, camera_location: r.camera_location })}
                        style={{
                          position: 'relative', borderRadius: 6, overflow: 'hidden',
                          border: '1px solid var(--border)', cursor: 'pointer', transition: 'all .2s',
                        }}
                        onMouseEnter={e => {
                          e.currentTarget.style.borderColor = 'var(--accent)'
                          e.currentTarget.style.transform = 'scale(1.03)'
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.borderColor = 'var(--border)'
                          e.currentTarget.style.transform = 'scale(1)'
                        }}
                      >
                        <img
                          src={frameUrl(a.frame_path)} alt=""
                          style={{ width: '100%', aspectRatio: '16/9', objectFit: 'cover', display: 'block', background: 'var(--bg-base)' }}
                          onError={e => { e.target.style.display = 'none' }}
                        />
                        <div style={{
                          position: 'absolute', bottom: 0, left: 0, right: 0,
                          background: 'linear-gradient(transparent, rgba(0,0,0,.8))',
                          padding: '10px 6px 4px', display: 'flex', justifyContent: 'space-between',
                        }}>
                          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-1)' }}>
                            <ClockCircleOutlined style={{ marginRight: 3 }} />{fmtTime(a.frame_time)}
                          </span>
                          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--green)' }}>
                            {(a.score * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                  {r.appearances.length > 8 && (
                    <div style={{ marginTop: 8, color: 'var(--text-3)', fontSize: 12, fontFamily: 'var(--mono)' }}>
                      共出现 {r.appearances.length} 次，显示前 8 条
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 检测图放大 Modal：点击人物框直接触发搜索 */}
      <Modal
        open={zoomOpen}
        onCancel={() => { setZoomOpen(false); modalHovRef.current = -1 }}
        footer={null}
        width={860}
        centered
        title={
          <span style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--accent)' }}>
            检测到 {persons.length} 个人物 · 点击框内人物进行查询
          </span>
        }
      >
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <canvas
            ref={modalCanvasRef}
            style={{ maxWidth: '100%', display: 'block', borderRadius: 6 }}
            onMouseMove={handleModalMouseMove}
            onMouseLeave={handleModalMouseLeave}
            onClick={handleModalClick}
          />
        </div>
        {/* 颜色图例 */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
          {persons.map((p, i) => (
            <Tag
              key={i}
              style={{
                borderColor: PERSON_COLORS[i % PERSON_COLORS.length],
                color: PERSON_COLORS[i % PERSON_COLORS.length],
                background: PERSON_COLORS[i % PERSON_COLORS.length] + '18',
                fontSize: 12,
              }}
            >
              P{i + 1} · {(p.confidence * 100).toFixed(0)}%
            </Tag>
          ))}
        </div>
        <div style={{ marginTop: 8, color: 'var(--text-3)', fontSize: 12, textAlign: 'center' }}>
          鼠标悬停高亮人物框，点击选择目标人物
        </div>
      </Modal>

      <FramePreviewModal
        open={!!enlarged}
        onClose={() => setEnlarged(null)}
        appearance={enlarged}
        videoInfo={enlarged && { video_id: enlarged.video_id, camera_location: enlarged.camera_location }}
      />
    </div>
  )
}
