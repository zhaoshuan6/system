import React, { useState, useEffect } from 'react'
import { Button, Select, Tag, Segmented, message } from 'antd'
import {
  PlayCircleOutlined, PauseCircleOutlined,
  ReloadOutlined, VideoCameraOutlined, PlaySquareOutlined
} from '@ant-design/icons'
import {
  getVideoSources, setVideoSource, getMonitorStatus,
  stopMonitor, streamUrl, videoFileUrl, getVideos
} from '../api.js'

export default function Monitor() {
  const [sources, setSources]       = useState([])
  const [dbVideos, setDbVideos]     = useState([])   // 数据库中已处理的视频
  const [selected, setSelected]     = useState(null) // 监控源 id
  const [playVideoId, setPlayVideoId] = useState(null) // 视频文件播放 id
  const [status, setStatus]         = useState({ is_active: false, type: null, fps: 0 })
  const [loading, setLoading]       = useState(false)
  const [mode, setMode]             = useState('live') // 'live' | 'file'
  const [streamKey, setStreamKey]   = useState(0)     // 强制刷新 MJPEG img

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    await Promise.all([loadSources(), loadStatus(), loadDbVideos()])
  }

  const loadSources = async () => {
    try {
      const { data } = await getVideoSources()
      setSources(data.sources || [])
    } catch { /* 忽略 */ }
  }

  const loadStatus = async () => {
    try {
      const { data } = await getMonitorStatus()
      setStatus(data)
    } catch { /* 忽略 */ }
  }

  const loadDbVideos = async () => {
    try {
      const { data } = await getVideos()
      setDbVideos(data.videos || [])
    } catch { /* 忽略 */ }
  }

  const handleStart = async () => {
    if (!selected) return message.warning('请先选择视频源')
    const src = sources.find(s => s.id === selected)
    if (!src) return
    setLoading(true)
    try {
      await setVideoSource(src.type, src.value)
      setStreamKey(k => k + 1)
      await loadStatus()
      message.success('监控已启动')
    } catch (e) {
      message.error(`启动失败: ${e?.response?.data?.error || e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleStop = async () => {
    try {
      await stopMonitor()
      await loadStatus()
      message.info('监控已停止')
    } catch { message.error('停止失败') }
  }

  const selectedSrc = sources.find(s => s.id === selected)

  return (
    <div style={{ padding: 24, height: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* 标题 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ color: 'var(--text-1)', fontSize: 20, fontWeight: 700, marginBottom: 2 }}>
            实时监控
          </h2>
          <p style={{ color: 'var(--text-3)', fontSize: 12, fontFamily: 'var(--mono)' }}>
            LIVE MONITOR · MJPEG / HTML5 VIDEO
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Segmented
            value={mode}
            onChange={setMode}
            options={[
              { value: 'live',  label: '直播流',   icon: <VideoCameraOutlined /> },
              { value: 'file',  label: '视频文件', icon: <PlaySquareOutlined /> },
            ]}
            style={{ background: 'var(--bg-panel)' }}
          />
          <Tag color={status.is_active ? 'cyan' : 'default'}>
            {status.is_active ? '● 直播中' : '● 未激活'}
          </Tag>
        </div>
      </div>

      {/* ── 直播流模式控制栏 ── */}
      {mode === 'live' && (
        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <Select
            placeholder="选择摄像头或视频源"
            style={{ width: 280 }}
            value={selected}
            onChange={setSelected}
            options={sources.map(s => ({
              value: s.id,
              label: (
                <span>
                  <Tag color={s.type === 'camera' ? 'blue' : 'purple'} style={{ marginRight: 6, fontSize: 10 }}>
                    {s.type === 'camera' ? '摄像头' : '视频'}
                  </Tag>
                  {s.name}
                </span>
              )
            }))}
          />
          <Button type="primary" icon={<PlayCircleOutlined />} loading={loading} onClick={handleStart}>
            启动
          </Button>
          <Button icon={<PauseCircleOutlined />} onClick={handleStop}
            disabled={!status.is_active}
            style={{ borderColor: 'var(--border)', color: 'var(--text-2)' }}>
            停止
          </Button>
          <Button icon={<ReloadOutlined />} onClick={loadAll}
            style={{ borderColor: 'var(--border)', color: 'var(--text-2)' }}>
            刷新
          </Button>
          <span style={{ color: 'var(--text-3)', fontSize: 12, marginLeft: 8 }}>
            ⚠️ 直播流模式不支持进度条，如需控制播放请切换到「视频文件」模式
          </span>
        </div>
      )}

      {/* ── 视频文件模式控制栏 ── */}
      {mode === 'file' && (
        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <PlaySquareOutlined style={{ color: 'var(--accent)', fontSize: 16 }} />
          <Select
            placeholder="选择已处理的视频"
            style={{ width: 320 }}
            value={playVideoId}
            onChange={setPlayVideoId}
            options={dbVideos.map(v => ({
              value: v.video_id,
              label: `[ID:${v.video_id}] ${v.camera_location} · ${v.frame_count}帧 · ${v.duration ? v.duration.toFixed(0)+'s' : '?'}`
            }))}
          />
          <Button icon={<ReloadOutlined />} onClick={loadDbVideos}
            style={{ borderColor: 'var(--border)', color: 'var(--text-2)' }}>
            刷新列表
          </Button>
          <span style={{ color: 'var(--green)', fontSize: 12, marginLeft: 8 }}>
            ✅ 视频文件模式支持：进度条拖动 / 暂停 / 快进后退
          </span>
        </div>
      )}

      {/* 视频画面区 */}
      <div style={{ flex: 1, display: 'flex', gap: 16, minHeight: 0 }}>

        {/* 主画面 */}
        <div style={{
          flex: 1, background: 'var(--bg-panel)',
          border: '1px solid var(--border)', borderRadius: 8,
          overflow: 'hidden', position: 'relative',
        }}>
          {/* 角标装饰 */}
          {['tl','tr','bl','br'].map(pos => (
            <div key={pos} style={{
              position: 'absolute', zIndex: 2,
              top:    pos[0]==='t' ? 12 : 'auto',
              bottom: pos[0]==='b' ? 12 : 'auto',
              left:   pos[1]==='l' ? 12 : 'auto',
              right:  pos[1]==='r' ? 12 : 'auto',
              width: 16, height: 16,
              borderTop:    pos[0]==='t' ? '2px solid var(--accent)' : 'none',
              borderBottom: pos[0]==='b' ? '2px solid var(--accent)' : 'none',
              borderLeft:   pos[1]==='l' ? '2px solid var(--accent)' : 'none',
              borderRight:  pos[1]==='r' ? '2px solid var(--accent)' : 'none',
            }} />
          ))}

          {/* 视频文件模式：HTML5 <video>，浏览器原生进度条 */}
          {mode === 'file' && playVideoId ? (
            <video
              key={playVideoId}
              src={videoFileUrl(playVideoId)}
              controls
              muted
              autoPlay
              crossOrigin="anonymous"
              preload="auto"
              onLoadedMetadata={e => e.target.play().catch(()=>{})}
              onError={e => console.error('video error', e.target.error)}
              style={{ width: '100%', height: '100%', objectFit: 'contain', background: '#000', display: 'block' }}
            />
          ) : mode === 'file' ? (
            <Placeholder icon={<PlaySquareOutlined style={{ fontSize: 48 }} />}
              text="请在上方选择视频进行播放" />

          /* 直播流模式：MJPEG <img> */
          ) : status.is_active ? (
            <img
              key={streamKey}
              src={`${streamUrl}?t=${streamKey}`}
              alt="监控画面"
              style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }}
            />
          ) : (
            <Placeholder icon={<VideoCameraOutlined style={{ fontSize: 48 }} />}
              text="请选择视频源并点击启动" />
          )}

          {/* 直播时间戳浮层 */}
          {mode === 'live' && status.is_active && (
            <div style={{
              position: 'absolute', bottom: 16, left: 16, zIndex: 3,
              fontFamily: 'var(--mono)', fontSize: 11,
              color: 'var(--accent)', background: 'rgba(0,0,0,.6)',
              padding: '3px 8px', borderRadius: 4,
            }}>
              {new Date().toLocaleString('zh-CN')}
            </div>
          )}
        </div>

        {/* 右侧信息面板 */}
        <div style={{ width: 200, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* 当前状态 */}
          <div className="card" style={{ padding: 16 }}>
            <Label>状态信息</Label>
            {[
              ['播放模式', mode === 'file' ? '视频文件' : '直播流'],
              ['进度控制', mode === 'file' ? '✅ 支持' : '❌ 不支持'],
              ['直播状态', status.is_active ? '运行中' : '已停止'],
              ['帧率',     status.fps ? `${Math.round(status.fps)} fps` : '—'],
            ].map(([k, v]) => (
              <Row key={k} label={k} value={v}
                highlight={k === '直播状态' && status.is_active} />
            ))}
          </div>

          {/* 可用视频源列表 */}
          <div className="card" style={{ padding: 16, flex: 1, overflow: 'auto' }}>
            <Label>视频源 ({sources.length})</Label>
            {sources.length === 0 && (
              <div style={{ color: 'var(--text-3)', fontSize: 12 }}>暂无可用视频源</div>
            )}
            {sources.map(s => (
              <SourceItem
                key={s.id}
                source={s}
                active={selected === s.id}
                onClick={() => setSelected(s.id)}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── 小组件 ──

function Placeholder({ icon, text }) {
  return (
    <div style={{
      width: '100%', height: '100%',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      gap: 12, color: 'var(--text-3)',
    }}>
      {icon}
      <div style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>{text}</div>
    </div>
  )
}

function Label({ children }) {
  return (
    <div style={{
      fontSize: 11, color: 'var(--text-3)',
      fontFamily: 'var(--mono)', textTransform: 'uppercase',
      marginBottom: 10, letterSpacing: '0.5px'
    }}>
      {children}
    </div>
  )
}

function Row({ label, value, highlight }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 7 }}>
      <span style={{ color: 'var(--text-3)', fontSize: 11 }}>{label}</span>
      <span style={{
        color: highlight ? 'var(--green)' : 'var(--text-1)',
        fontSize: 11, fontFamily: 'var(--mono)', maxWidth: 90, textAlign: 'right'
      }}>{value}</span>
    </div>
  )
}

function SourceItem({ source, active, onClick }) {
  return (
    <div onClick={onClick} style={{
      padding: '7px 10px', borderRadius: 6, marginBottom: 5, cursor: 'pointer',
      background: active ? 'var(--accent-glow)' : 'var(--bg-base)',
      border: `1px solid ${active ? 'var(--accent-dim)' : 'var(--border)'}`,
      transition: 'all .15s',
    }}>
      <div style={{ fontSize: 11, color: active ? 'var(--accent)' : 'var(--text-1)' }}>
        {source.name}
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>
        {source.type}
      </div>
    </div>
  )
}
