import React, { useState, useEffect, useCallback } from 'react'
import { Table, Tag, Button, Popconfirm, message, Image, Tooltip, Space, Radio } from 'antd'
import {
  DeleteOutlined, ClearOutlined, SearchOutlined,
  PictureOutlined, EnvironmentOutlined, ReloadOutlined,
} from '@ant-design/icons'
import { getHistory, deleteHistory, clearHistory, frameUrl } from '../api.js'

const BASE = 'http://localhost:5000'

// 搜索类型配置
const TYPE_CONFIG = {
  text:       { label: '文字搜索', color: 'blue',   icon: <SearchOutlined /> },
  image:      { label: '图片搜索', color: 'purple', icon: <PictureOutlined /> },
  trajectory: { label: '轨迹追踪', color: 'cyan',   icon: <EnvironmentOutlined /> },
}

const queryImageUrl = (path) =>
  path ? `${BASE}/api/data/frame?path=${encodeURIComponent(path)}` : null

export default function SearchHistory({ isSuperuser }) {
  const [records, setRecords]   = useState([])
  const [total, setTotal]       = useState(0)
  const [loading, setLoading]   = useState(false)
  const [typeFilter, setTypeFilter] = useState('all')
  const [page, setPage]         = useState(1)
  const perPage = 20

  const fetchHistory = useCallback(async (p = page, type = typeFilter) => {
    setLoading(true)
    try {
      const params = { page: p, per_page: perPage }
      if (type !== 'all') params.type = type
      const { data } = await getHistory(params)
      setRecords(data.records || [])
      setTotal(data.total || 0)
    } catch (e) {
      message.error('获取历史失败')
    } finally {
      setLoading(false)
    }
  }, [page, typeFilter])

  useEffect(() => { fetchHistory(1, typeFilter) }, [typeFilter])

  const handleTypeChange = (e) => {
    setTypeFilter(e.target.value)
    setPage(1)
  }

  const handleDelete = async (id) => {
    try {
      await deleteHistory(id)
      message.success('已删除')
      fetchHistory(page, typeFilter)
    } catch (e) {
      message.error(e?.response?.data?.error || '删除失败')
    }
  }

  const handleClear = async () => {
    try {
      const type = typeFilter !== 'all' ? typeFilter : undefined
      const { data } = await clearHistory(type)
      message.success(data.message)
      setPage(1)
      fetchHistory(1, typeFilter)
    } catch (e) {
      message.error('清空失败')
    }
  }

  const columns = [
    {
      title: '类型',
      dataIndex: 'search_type',
      width: 110,
      render: (type) => {
        const cfg = TYPE_CONFIG[type] || { label: type, color: 'default', icon: null }
        return (
          <Tag icon={cfg.icon} color={cfg.color} style={{ fontSize: 12 }}>
            {cfg.label}
          </Tag>
        )
      },
    },
    {
      title: '搜索内容',
      key: 'query',
      render: (_, record) => {
        if (record.search_type === 'text') {
          return (
            <span style={{ color: 'var(--text-1)', fontSize: 13 }}>
              {record.query_text}
            </span>
          )
        }
        if (record.query_image) {
          return (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Image
                src={queryImageUrl(record.query_image)}
                width={48}
                height={36}
                style={{ objectFit: 'cover', borderRadius: 4, border: '1px solid var(--border)' }}
                preview={{ mask: false }}
                fallback="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='48' height='36'%3E%3Crect fill='%23222'/%3E%3C/svg%3E"
              />
              <span style={{ color: 'var(--text-3)', fontSize: 11, fontFamily: 'var(--mono)' }}>
                {record.query_image.split(/[\\/]/).pop()}
              </span>
            </div>
          )
        }
        return <span style={{ color: 'var(--text-3)' }}>—</span>
      },
    },
    {
      title: '命中结果',
      dataIndex: 'result_count',
      width: 90,
      align: 'center',
      render: (v) => (
        <span style={{
          fontFamily: 'var(--mono)', fontSize: 13,
          color: v > 0 ? 'var(--green)' : 'var(--text-3)',
        }}>
          {v}
        </span>
      ),
    },
    ...(isSuperuser ? [{
      title: '操作用户',
      dataIndex: 'username',
      width: 120,
      render: (name) => (
        <span style={{ fontSize: 12, color: 'var(--accent)', fontFamily: 'var(--mono)' }}>
          {name}
        </span>
      ),
    }] : []),
    {
      title: '搜索时间',
      dataIndex: 'created_at',
      width: 160,
      render: (t) => {
        if (!t) return '—'
        const d = new Date(t)
        return (
          <span style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--text-3)' }}>
            {d.toLocaleString('zh-CN', {
              month: '2-digit', day: '2-digit',
              hour: '2-digit', minute: '2-digit', second: '2-digit',
              hour12: false,
            })}
          </span>
        )
      },
    },
    {
      title: '操作',
      width: 70,
      align: 'center',
      render: (_, record) => (
        <Popconfirm
          title="确认删除这条记录？"
          onConfirm={() => handleDelete(record.id)}
          okText="删除" cancelText="取消"
          okButtonProps={{ danger: true }}
        >
          <Tooltip title="删除">
            <Button
              type="text" size="small" danger
              icon={<DeleteOutlined />}
            />
          </Tooltip>
        </Popconfirm>
      ),
    },
  ]

  const clearLabel = typeFilter === 'all'
    ? (isSuperuser ? '清空全部' : '清空我的历史')
    : `清空${TYPE_CONFIG[typeFilter]?.label || ''}记录`

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20, height: '100%' }}>
      {/* 标题 */}
      <div>
        <h2 style={{ color: 'var(--text-1)', fontSize: 20, fontWeight: 700, marginBottom: 2 }}>
          搜索历史
        </h2>
        <p style={{ color: 'var(--text-3)', fontSize: 12, fontFamily: 'var(--mono)' }}>
          SEARCH HISTORY · {isSuperuser ? 'ALL USERS' : 'MY RECORDS'}
        </p>
      </div>

      {/* 工具栏 */}
      <div className="card" style={{ padding: '14px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          {/* 类型筛选 */}
          <Radio.Group
            value={typeFilter}
            onChange={handleTypeChange}
            buttonStyle="solid"
            size="small"
          >
            <Radio.Button value="all">全部</Radio.Button>
            <Radio.Button value="text">
              <SearchOutlined style={{ marginRight: 4 }} />文字搜索
            </Radio.Button>
            <Radio.Button value="image">
              <PictureOutlined style={{ marginRight: 4 }} />图片搜索
            </Radio.Button>
            <Radio.Button value="trajectory">
              <EnvironmentOutlined style={{ marginRight: 4 }} />轨迹追踪
            </Radio.Button>
          </Radio.Group>

          {/* 右侧操作按钮 */}
          <Space>
            <Button
              icon={<ReloadOutlined />}
              size="small"
              onClick={() => fetchHistory(page, typeFilter)}
              style={{ borderColor: 'var(--border)', color: 'var(--text-2)' }}
            >
              刷新
            </Button>
            <Popconfirm
              title={`确认${clearLabel}？此操作不可恢复。`}
              onConfirm={handleClear}
              okText="确认清空" cancelText="取消"
              okButtonProps={{ danger: true }}
              disabled={total === 0}
            >
              <Button
                icon={<ClearOutlined />}
                size="small"
                danger
                disabled={total === 0}
              >
                {clearLabel}
              </Button>
            </Popconfirm>
          </Space>
        </div>
      </div>

      {/* 统计行 */}
      <div style={{ color: 'var(--text-3)', fontSize: 12, fontFamily: 'var(--mono)', marginBottom: -8 }}>
        共 <span style={{ color: 'var(--accent)' }}>{total}</span> 条记录
      </div>

      {/* 表格 */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        <Table
          columns={columns}
          dataSource={records}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={{
            current: page,
            pageSize: perPage,
            total,
            showSizeChanger: false,
            showQuickJumper: true,
            onChange: (p) => { setPage(p); fetchHistory(p, typeFilter) },
            style: { marginTop: 16 },
          }}
          locale={{ emptyText: <span style={{ color: 'var(--text-3)' }}>暂无搜索记录</span> }}
          style={{ background: 'transparent' }}
          rowClassName={() => 'history-row'}
        />
      </div>
    </div>
  )
}
