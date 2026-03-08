import React, { useState } from 'react'
import { Upload, Button, Slider, Tag, Modal, message, Empty } from 'antd'
import { InboxOutlined, SearchOutlined, ClockCircleOutlined, EnvironmentOutlined, UserOutlined } from '@ant-design/icons'
import { searchByImage, frameUrl } from '../api.js'

const { Dragger } = Upload

export default function ImageSearch() {
  const [file, setFile]       = useState(null)
  const [preview, setPreview] = useState(null) // 上传图片预览URL
  const [topK, setTopK]       = useState(10)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [enlarged, setEnlarged] = useState(null)
  const [detected, setDetected] = useState(false)

  const handleFileChange = (info) => {
    const f = info.file.originFileObj || info.file
    if (f) {
      setFile(f)
      setPreview(URL.createObjectURL(f))
      setResults(null)
    }
    return false
  }

  const handleSearch = async () => {
    if (!file) return message.warning('请先上传查询图片')
    setLoading(true)
    setResults(null)
    try {
      const { data } = await searchByImage(file, topK)
      setResults(data.results || [])
      setDetected(data.detected_person)
      if ((data.results || []).length === 0) message.info('未找到匹配人物')
    } catch (e) {
      message.error(`搜索失败: ${e?.response?.data?.error || e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const fmtTime = (sec) => {
    const m = Math.floor(sec / 60).toString().padStart(2, '0')
    const s = Math.floor(sec % 60).toString().padStart(2, '0')
    return `${m}:${s}`
  }

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20, height: '100%' }}>
      {/* 标题 */}
      <div>
        <h2 style={{ color: 'var(--text-1)', fontSize: 20, fontWeight: 700, marginBottom: 2 }}>以图搜图</h2>
        <p style={{ color: 'var(--text-3)', fontSize: 12, fontFamily: 'var(--mono)' }}>
          IMAGE-TO-VIDEO SEARCH · YOLOV8 + CLIP
        </p>
      </div>

      <div style={{ display: 'flex', gap: 20, flex: 1, overflow: 'hidden' }}>
        {/* 左侧：上传区 */}
        <div style={{ width: 280, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card" style={{ padding: 16 }}>
            <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 12, fontFamily: 'var(--mono)', textTransform: 'uppercase' }}>
              上传查询图片
            </div>

            {preview ? (
              <div>
                <div style={{ position: 'relative', borderRadius: 8, overflow: 'hidden', marginBottom: 10 }}>
                  <img src={preview} alt="查询图片" style={{ width: '100%', display: 'block', maxHeight: 200, objectFit: 'contain', background: 'var(--bg-base)' }} />
                  {detected && (
                    <Tag
                      icon={<UserOutlined />}
                      color="cyan"
                      style={{ position: 'absolute', top: 8, left: 8, fontSize: 10 }}
                    >
                      已检测到人物
                    </Tag>
                  )}
                </div>
                <Button
                  block
                  onClick={() => { setFile(null); setPreview(null); setResults(null) }}
                  style={{ borderColor: 'var(--border)', color: 'var(--text-2)', marginBottom: 8 }}
                >
                  重新选择
                </Button>
              </div>
            ) : (
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
          </div>

          {/* 参数 */}
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
            <Button
              type="primary" block
              icon={<SearchOutlined />}
              loading={loading}
              onClick={handleSearch}
              style={{ marginTop: 16 }}
              disabled={!file}
            >
              开始搜索
            </Button>
          </div>

          {/* 说明 */}
          <div className="card" style={{ padding: 16, fontSize: 12, color: 'var(--text-3)', lineHeight: 1.8 }}>
            <div style={{ color: 'var(--text-2)', marginBottom: 8 }}>📖 使用说明</div>
            <div>1. 上传包含目标人物的图片</div>
            <div>2. 系统自动用 YOLOv8 检测人物并裁剪</div>
            <div>3. CLIP 提取特征后在数据库中检索</div>
            <div>4. 返回该人物在各视频中的出现记录</div>
          </div>
        </div>

        {/* 右侧：结果区 */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          {results === null && !loading && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <div style={{ textAlign: 'center', color: 'var(--text-3)' }}>
                <UserOutlined style={{ fontSize: 48, marginBottom: 16 }} />
                <div style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>上传图片后点击搜索</div>
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

                  {/* 关键帧网格 */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 8 }}>
                    {r.appearances.slice(0, 8).map((a, j) => (
                      <div
                        key={j}
                        onClick={() => setEnlarged({ src: frameUrl(a.frame_path), time: a.frame_time, score: a.score })}
                        style={{
                          position: 'relative', borderRadius: 6, overflow: 'hidden',
                          border: '1px solid var(--border)', cursor: 'pointer',
                          transition: 'all .2s',
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
                          src={frameUrl(a.frame_path)}
                          alt=""
                          style={{ width: '100%', aspectRatio: '16/9', objectFit: 'cover', display: 'block', background: 'var(--bg-base)' }}
                          onError={e => { e.target.style.display = 'none' }}
                        />
                        <div style={{
                          position: 'absolute', bottom: 0, left: 0, right: 0,
                          background: 'linear-gradient(transparent, rgba(0,0,0,.8))',
                          padding: '10px 6px 4px',
                          display: 'flex', justifyContent: 'space-between',
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

      {/* 放大预览 */}
      <Modal
        open={!!enlarged}
        onCancel={() => setEnlarged(null)}
        footer={null} width={800}
        title={enlarged && (
          <span style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--accent)' }}>
            时间: {fmtTime(enlarged.time)} · 相似度: {(enlarged.score * 100).toFixed(1)}%
          </span>
        )}
      >
        {enlarged && <img src={enlarged.src} alt="预览" style={{ width: '100%', borderRadius: 6 }} />}
      </Modal>
    </div>
  )
}
