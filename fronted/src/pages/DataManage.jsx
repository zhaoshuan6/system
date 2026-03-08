import React, { useState, useEffect } from 'react'
import { Upload, Button, Input, InputNumber, Table, Tag, Modal, Progress, message, Popconfirm } from 'antd'
import { InboxOutlined, ReloadOutlined, DeleteOutlined, EyeOutlined, DatabaseOutlined } from '@ant-design/icons'
import { getVideos, deleteVideo, uploadVideo, rebuildIndex, frameUrl } from '../api.js'

const { Dragger } = Upload

export default function DataManage() {
  const [videos, setVideos]         = useState([])
  const [loading, setLoading]       = useState(false)
  const [uploading, setUploading]   = useState(false)
  const [uploadPct, setUploadPct]   = useState(0)
  const [detailVideo, setDetailVideo] = useState(null)

  // 上传表单
  const [uploadFile, setUploadFile]       = useState(null)
  const [cameraId, setCameraId]           = useState(1)
  const [cameraLocation, setCameraLocation] = useState('')
  const [interval, setInterval]           = useState(10)

  useEffect(() => { loadVideos() }, [])

  const loadVideos = async () => {
    setLoading(true)
    try {
      const { data } = await getVideos()
      setVideos(data.videos || [])
    } catch { message.error('获取视频列表失败') }
    finally { setLoading(false) }
  }

  const handleUpload = async () => {
    if (!uploadFile) return message.warning('请选择视频文件')
    if (!cameraLocation.trim()) return message.warning('请填写摄像头位置')
    setUploading(true)
    setUploadPct(10)
    try {
      // 模拟进度
      const timer = setInterval(() => setUploadPct(p => Math.min(p + 5, 90)), 2000)
      await uploadVideo(uploadFile, cameraId, cameraLocation, interval)
      clearInterval(timer)
      setUploadPct(100)
      message.success('视频处理完成！')
      setUploadFile(null)
      loadVideos()
    } catch (e) {
      message.error(`上传失败: ${e?.response?.data?.error || e.message}`)
    } finally {
      setUploading(false)
      setTimeout(() => setUploadPct(0), 1000)
    }
  }

  const handleDelete = async (videoId) => {
    try {
      await deleteVideo(videoId)
      message.success('删除成功')
      loadVideos()
    } catch { message.error('删除失败') }
  }

  const handleRebuild = async () => {
    try {
      const { data } = await rebuildIndex()
      message.success(`索引重建完成，共 ${data.indexed_vectors} 条向量`)
    } catch { message.error('重建失败') }
  }

  const columns = [
    {
      title: 'ID', dataIndex: 'video_id', width: 60,
      render: v => <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>#{v}</span>
    },
    {
      title: '摄像头位置', dataIndex: 'camera_location', width: 160,
      render: v => <Tag color="blue">{v || '未知'}</Tag>
    },
    {
      title: '时长(秒)', dataIndex: 'duration', width: 90,
      render: v => <span style={{ fontFamily: 'var(--mono)' }}>{v ? v.toFixed(0) : '—'}</span>
    },
    {
      title: '关键帧', dataIndex: 'frame_count', width: 80,
      render: v => <span style={{ fontFamily: 'var(--mono)', color: 'var(--green)' }}>{v}</span>
    },
    {
      title: '检测人物', dataIndex: 'object_count', width: 80,
      render: v => <span style={{ fontFamily: 'var(--mono)', color: 'var(--yellow)' }}>{v}</span>
    },
    {
      title: '入库时间', dataIndex: 'created_at', width: 160,
      render: v => v ? <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-3)' }}>
        {new Date(v).toLocaleString('zh-CN')}
      </span> : '—'
    },
    {
      title: '操作', width: 100, fixed: 'right',
      render: (_, row) => (
        <div style={{ display: 'flex', gap: 8 }}>
          <Button
            size="small" icon={<EyeOutlined />}
            onClick={() => setDetailVideo(row)}
            style={{ borderColor: 'var(--border)', color: 'var(--text-2)' }}
          />
          <Popconfirm
            title="确认删除该视频及所有关联数据？"
            onConfirm={() => handleDelete(row.video_id)}
            okText="删除" cancelText="取消"
          >
            <Button size="small" icon={<DeleteOutlined />} danger />
          </Popconfirm>
        </div>
      )
    }
  ]

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20, height: '100%', overflow: 'auto' }}>
      {/* 标题 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ color: 'var(--text-1)', fontSize: 20, fontWeight: 700, marginBottom: 2 }}>数据管理</h2>
          <p style={{ color: 'var(--text-3)', fontSize: 12, fontFamily: 'var(--mono)' }}>
            DATA MANAGEMENT · MySQL + FAISS
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <Button icon={<ReloadOutlined />} onClick={loadVideos} style={{ borderColor: 'var(--border)', color: 'var(--text-2)' }}>
            刷新
          </Button>
          <Button icon={<DatabaseOutlined />} onClick={handleRebuild} style={{ borderColor: 'var(--accent-dim)', color: 'var(--accent)' }}>
            重建索引
          </Button>
        </div>
      </div>

      {/* 统计卡片 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {[
          { label: '视频总数', value: videos.length, color: 'var(--accent)' },
          { label: '关键帧总数', value: videos.reduce((s, v) => s + v.frame_count, 0), color: 'var(--green)' },
          { label: '检测人物总数', value: videos.reduce((s, v) => s + v.object_count, 0), color: 'var(--yellow)' },
        ].map(item => (
          <div key={item.label} className="card" style={{ textAlign: 'center', padding: 20 }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: item.color, fontFamily: 'var(--mono)' }}>
              {item.value}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 4 }}>{item.label}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 20 }}>
        {/* 上传视频 */}
        <div className="card" style={{ width: 320, flexShrink: 0, padding: 20 }}>
          <div style={{ fontSize: 12, color: 'var(--text-3)', fontFamily: 'var(--mono)', textTransform: 'uppercase', marginBottom: 16 }}>
            上传新视频
          </div>

          <Dragger
            accept=".mp4,.avi,.mov,.mkv"
            beforeUpload={() => false}
            onChange={info => {
              const f = info.file.originFileObj || info.file
              if (f) setUploadFile(f)
              return false
            }}
            showUploadList={false}
            style={{ marginBottom: 14 }}
          >
            <div style={{ padding: '16px 10px', textAlign: 'center' }}>
              <InboxOutlined style={{ fontSize: 32, color: uploadFile ? 'var(--green)' : 'var(--accent)', marginBottom: 8 }} />
              <div style={{ color: 'var(--text-2)', fontSize: 12 }}>
                {uploadFile ? uploadFile.name : '点击或拖拽视频文件'}
              </div>
              <div style={{ color: 'var(--text-3)', fontSize: 11, marginTop: 4 }}>MP4 / AVI / MOV / MKV</div>
            </div>
          </Dragger>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 4 }}>摄像头位置 *</div>
              <Input
                placeholder="如：图书馆门口、食堂入口"
                value={cameraLocation}
                onChange={e => setCameraLocation(e.target.value)}
              />
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 4 }}>摄像头 ID</div>
                <InputNumber min={1} value={cameraId} onChange={setCameraId} style={{ width: '100%', background: 'var(--bg-base)', borderColor: 'var(--border)' }} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 4 }}>帧间隔(秒)</div>
                <InputNumber min={1} max={60} value={interval} onChange={setInterval} style={{ width: '100%', background: 'var(--bg-base)', borderColor: 'var(--border)' }} />
              </div>
            </div>
          </div>

          {uploadPct > 0 && (
            <Progress percent={uploadPct} strokeColor="var(--accent)" trailColor="var(--border)" style={{ marginTop: 12 }} />
          )}

          <Button
            type="primary" block
            loading={uploading}
            onClick={handleUpload}
            style={{ marginTop: 14 }}
            disabled={!uploadFile}
          >
            {uploading ? '处理中（可能需要几分钟）...' : '上传并处理'}
          </Button>
        </div>

        {/* 视频列表 */}
        <div style={{ flex: 1 }}>
          <Table
            dataSource={videos}
            columns={columns}
            rowKey="video_id"
            loading={loading}
            pagination={{ pageSize: 10, size: 'small' }}
            scroll={{ x: 700 }}
            style={{ background: 'transparent' }}
          />
        </div>
      </div>

      {/* 视频详情弹窗 */}
      <Modal
        open={!!detailVideo}
        onCancel={() => setDetailVideo(null)}
        footer={null}
        width={900}
        title={detailVideo && (
          <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>
            视频详情 · ID: {detailVideo.video_id} · {detailVideo.camera_location}
          </span>
        )}
      >
        {detailVideo && (
          <div>
            <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
              {[
                ['文件路径', detailVideo.file_path],
                ['时长', detailVideo.duration ? `${detailVideo.duration.toFixed(0)} 秒` : '—'],
                ['关键帧', detailVideo.frame_count],
                ['检测人物', detailVideo.object_count],
              ].map(([k, v]) => (
                <div key={k} style={{ flex: '1 1 200px' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 3 }}>{k}</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--text-1)', wordBreak: 'break-all' }}>{v}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
