import React, { useState } from 'react'
import { Input, Button, Slider, Tag, Modal, message, Empty } from 'antd'
import { SearchOutlined, ClockCircleOutlined, EnvironmentOutlined } from '@ant-design/icons'
import { searchByText, frameUrl } from '../api.js'

export default function TextSearch() {
  const [query, setQuery]     = useState('')
  const [topK, setTopK]       = useState(10)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [preview, setPreview] = useState(null) // {src, time, score}

  const handleSearch = async () => {
    if (!query.trim()) return message.warning('请输入搜索描述')
    setLoading(true)
    setResults(null)
    try {
      const { data } = await searchByText(query.trim(), topK)
      setResults(data.results || [])
      if ((data.results || []).length === 0) message.info('未找到匹配结果')
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
        <h2 style={{ color: 'var(--text-1)', fontSize: 20, fontWeight: 700, marginBottom: 2 }}>文字搜图</h2>
        <p style={{ color: 'var(--text-3)', fontSize: 12, fontFamily: 'var(--mono)' }}>
          TEXT-TO-VIDEO SEARCH · CLIP MODEL
        </p>
      </div>

      {/* 搜索框 */}
      <div className="card">
        <div style={{ marginBottom: 12, color: 'var(--text-2)', fontSize: 13 }}>
          用自然语言描述你要找的人物，例如：
          <span style={{ color: 'var(--accent)', marginLeft: 6, fontStyle: 'italic' }}>
            "穿红色外套戴黑色帽子的男生"
          </span>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <Input
            size="large"
            placeholder="输入人物描述，如：穿蓝色上衣的人"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onPressEnter={handleSearch}
            prefix={<SearchOutlined style={{ color: 'var(--text-3)' }} />}
            style={{ flex: 1 }}
          />
          <Button
            type="primary" size="large"
            loading={loading} onClick={handleSearch}
            style={{ minWidth: 100 }}
          >
            搜索
          </Button>
        </div>
        <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ color: 'var(--text-3)', fontSize: 12, whiteSpace: 'nowrap' }}>
            返回视频数：{topK}
          </span>
          <Slider
            min={1} max={20} value={topK}
            onChange={setTopK}
            style={{ flex: 1, maxWidth: 200 }}
            trackStyle={{ background: 'var(--accent)' }}
            handleStyle={{ borderColor: 'var(--accent)' }}
          />
        </div>
        {/* 快捷示例 */}
        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {['穿黑色外套的人', '戴帽子的人', 'person walking', 'a person in red'].map(ex => (
            <Tag
              key={ex}
              onClick={() => setQuery(ex)}
              style={{ cursor: 'pointer', background: 'var(--bg-base)', borderColor: 'var(--border)', color: 'var(--text-2)', fontSize: 12 }}
            >
              {ex}
            </Tag>
          ))}
        </div>
      </div>

      {/* 结果区 */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {results === null && !loading && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300 }}>
            <div style={{ textAlign: 'center', color: 'var(--text-3)' }}>
              <SearchOutlined style={{ fontSize: 48, marginBottom: 16 }} />
              <div style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>输入描述后点击搜索</div>
            </div>
          </div>
        )}

        {results && results.length === 0 && (
          <Empty description={<span style={{ color: 'var(--text-3)' }}>未找到匹配结果，请换一种描述方式</span>} />
        )}

        {results && results.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ color: 'var(--text-3)', fontSize: 12, fontFamily: 'var(--mono)' }}>
              找到 <span style={{ color: 'var(--accent)' }}>{results.length}</span> 个相关视频
            </div>

            {results.map((r, i) => (
              <div key={r.video_id} className="card fade-in" style={{ animationDelay: `${i * 0.05}s` }}>
                {/* 视频标题行 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-3)' }}>#{i + 1}</span>
                  <span style={{ color: 'var(--accent)', fontWeight: 600, fontSize: 14 }}>
                    视频 ID: {r.video_id}
                  </span>
                  <Tag icon={<EnvironmentOutlined />} color="blue" style={{ fontSize: 11 }}>
                    {r.camera_location}
                  </Tag>
                  <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 12, color: 'var(--text-3)' }}>相似度</span>
                    <div style={{ width: 80 }}>
                      <div className="score-bar">
                        <div className="score-bar-fill" style={{ width: `${Math.round(r.max_score * 100)}%` }} />
                      </div>
                    </div>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--green)', minWidth: 40 }}>
                      {(r.max_score * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>

                {/* 关键帧图片墙 */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 8 }}>
                  {r.appearances.slice(0, 8).map((a, j) => (
                    <div
                      key={j}
                      onClick={() => setPreview({ src: frameUrl(a.frame_path), time: a.frame_time, score: a.score })}
                      style={{
                        position: 'relative', borderRadius: 6, overflow: 'hidden',
                        border: '1px solid var(--border)', cursor: 'pointer',
                        transition: 'border-color .2s, transform .2s',
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.borderColor = 'var(--accent)'
                        e.currentTarget.style.transform = 'scale(1.02)'
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.borderColor = 'var(--border)'
                        e.currentTarget.style.transform = 'scale(1)'
                      }}
                    >
                      <img
                        src={frameUrl(a.frame_path)}
                        alt={`t=${a.frame_time}`}
                        style={{ width: '100%', aspectRatio: '16/9', objectFit: 'cover', display: 'block', background: 'var(--bg-base)' }}
                        onError={e => { e.target.style.display = 'none' }}
                      />
                      <div style={{
                        position: 'absolute', bottom: 0, left: 0, right: 0,
                        background: 'linear-gradient(transparent, rgba(0,0,0,.8))',
                        padding: '12px 6px 4px',
                        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
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

      {/* 图片预览弹窗 */}
      <Modal
        open={!!preview}
        onCancel={() => setPreview(null)}
        footer={null}
        width={800}
        title={
          preview && (
            <span style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--accent)' }}>
              时间: {fmtTime(preview.time)} · 相似度: {(preview.score * 100).toFixed(1)}%
            </span>
          )
        }
      >
        {preview && (
          <img src={preview.src} alt="预览" style={{ width: '100%', borderRadius: 6 }} />
        )}
      </Modal>
    </div>
  )
}
