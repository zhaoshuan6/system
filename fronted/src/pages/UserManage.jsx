import React, { useState, useEffect } from 'react'
import { Button, Input, Table, Tag, Modal, Popconfirm, message, Switch } from 'antd'
import { PlusOutlined, ReloadOutlined, DeleteOutlined, EditOutlined, CrownOutlined, UserOutlined } from '@ant-design/icons'
import { getUsers, createUser, updateUser, deleteUser } from '../api.js'

export default function UserManage() {
  const [users, setUsers]       = useState([])
  const [loading, setLoading]   = useState(false)
  const [modal, setModal]       = useState(null)  // null | 'create' | 'edit'
  const [editTarget, setEditTarget] = useState(null)

  // 表单
  const [formUsername, setFormUsername] = useState('')
  const [formPassword, setFormPassword] = useState('')
  const [saving, setSaving]             = useState(false)

  useEffect(() => { load() }, [])

  const load = async () => {
    setLoading(true)
    try {
      const { data } = await getUsers()
      setUsers(data.users || [])
    } catch { message.error('获取用户列表失败') }
    finally { setLoading(false) }
  }

  const openCreate = () => {
    setFormUsername(''); setFormPassword('')
    setEditTarget(null); setModal('create')
  }

  const openEdit = (user) => {
    setFormPassword('')
    setEditTarget(user); setModal('edit')
  }

  const handleCreate = async () => {
    if (!formUsername.trim() || !formPassword.trim())
      return message.warning('请填写用户名和密码')
    setSaving(true)
    try {
      const { data } = await createUser(formUsername.trim(), formPassword.trim())
      if (data.success) {
        message.success(data.message)
        setModal(null); load()
      } else {
        message.error(data.error)
      }
    } catch (e) {
      message.error(e?.response?.data?.error || '创建失败')
    } finally { setSaving(false) }
  }

  const handleUpdate = async () => {
    if (!formPassword.trim())
      return message.warning('请输入新密码')
    setSaving(true)
    try {
      const { data } = await updateUser(editTarget.user_id, { password: formPassword.trim() })
      if (data.success) {
        message.success('密码已更新')
        setModal(null); load()
      } else {
        message.error(data.error)
      }
    } catch (e) {
      message.error(e?.response?.data?.error || '更新失败')
    } finally { setSaving(false) }
  }

  const handleToggleActive = async (user, checked) => {
    try {
      const { data } = await updateUser(user.user_id, { is_active: checked })
      if (data.success) {
        message.success(checked ? '账号已启用' : '账号已禁用')
        load()
      }
    } catch { message.error('操作失败') }
  }

  const handleDelete = async (userId) => {
    try {
      const { data } = await deleteUser(userId)
      if (data.success) { message.success(data.message); load() }
      else message.error(data.error)
    } catch (e) {
      message.error(e?.response?.data?.error || '删除失败')
    }
  }

  const columns = [
    {
      title: 'ID', dataIndex: 'user_id', width: 60,
      render: v => <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>#{v}</span>
    },
    {
      title: '用户名', dataIndex: 'username', width: 140,
      render: (v, row) => (
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {row.role === 'superuser'
            ? <CrownOutlined style={{ color: '#ffd700' }} />
            : <UserOutlined style={{ color: 'var(--text-3)' }} />}
          <span style={{ fontWeight: row.role === 'superuser' ? 700 : 400 }}>{v}</span>
        </span>
      )
    },
    {
      title: '角色', dataIndex: 'role', width: 120,
      render: v => (
        <Tag color={v === 'superuser' ? 'gold' : 'blue'} style={{ fontFamily: 'var(--mono)' }}>
          {v === 'superuser' ? '超级管理员' : '普通管理员'}
        </Tag>
      )
    },
    {
      title: '状态', dataIndex: 'is_active', width: 90,
      render: (v, row) => (
        row.role === 'superuser'
          ? <Tag color="green">启用</Tag>
          : <Switch
              checked={v} size="small"
              onChange={checked => handleToggleActive(row, checked)}
            />
      )
    },
    {
      title: '创建者', dataIndex: 'created_by', width: 110,
      render: v => <span style={{ fontSize: 12, color: 'var(--text-3)' }}>{v || '—'}</span>
    },
    {
      title: '创建时间', dataIndex: 'created_at', width: 160,
      render: v => v
        ? <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-3)' }}>
            {new Date(v).toLocaleString('zh-CN')}
          </span>
        : '—'
    },
    {
      title: '操作', width: 110, fixed: 'right',
      render: (_, row) => row.role === 'superuser' ? (
        <span style={{ fontSize: 12, color: 'var(--text-3)' }}>无法修改</span>
      ) : (
        <div style={{ display: 'flex', gap: 8 }}>
          <Button size="small" icon={<EditOutlined />}
            onClick={() => openEdit(row)}
            style={{ borderColor: 'var(--border)', color: 'var(--text-2)' }}
          />
          <Popconfirm
            title={`确认删除管理员 "${row.username}"？`}
            onConfirm={() => handleDelete(row.user_id)}
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
          <h2 style={{ color: 'var(--text-1)', fontSize: 20, fontWeight: 700, marginBottom: 2 }}>
            用户管理
          </h2>
          <p style={{ color: 'var(--text-3)', fontSize: 12, fontFamily: 'var(--mono)' }}>
            USER MANAGEMENT · 超级管理员专属
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <Button icon={<ReloadOutlined />} onClick={load}
            style={{ borderColor: 'var(--border)', color: 'var(--text-2)' }}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建管理员
          </Button>
        </div>
      </div>

      {/* 说明 */}
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-lit)',
        borderRadius: 8, padding: '12px 16px',
        fontSize: 12, color: 'var(--text-3)', lineHeight: 2,
      }}>
        <span style={{ color: '#ffd700', marginRight: 8 }}>👑 超级管理员</span>拥有全部权限，可查看文件路径、删除视频、管理用户
        <span style={{ margin: '0 12px', color: 'var(--border)' }}>|</span>
        <span style={{ color: 'var(--accent)', marginRight: 8 }}>👤 普通管理员</span>可使用搜索/监控/轨迹等功能，但不可查看文件路径、不可删除视频
      </div>

      {/* 统计 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {[
          { label: '用户总数', value: users.length, color: 'var(--accent)' },
          { label: '普通管理员', value: users.filter(u => u.role === 'admin').length, color: 'var(--green)' },
          { label: '当前启用', value: users.filter(u => u.is_active).length, color: 'var(--yellow)' },
        ].map(item => (
          <div key={item.label} className="card" style={{ textAlign: 'center', padding: 20 }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: item.color, fontFamily: 'var(--mono)' }}>
              {item.value}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 4 }}>{item.label}</div>
          </div>
        ))}
      </div>

      {/* 用户表 */}
      <Table
        dataSource={users}
        columns={columns}
        rowKey="user_id"
        loading={loading}
        pagination={{ pageSize: 10, size: 'small' }}
        scroll={{ x: 800 }}
        style={{ background: 'transparent' }}
      />

      {/* 创建/编辑弹窗 */}
      <Modal
        open={!!modal}
        onCancel={() => setModal(null)}
        onOk={modal === 'create' ? handleCreate : handleUpdate}
        okText={modal === 'create' ? '创建' : '保存'}
        cancelText="取消"
        confirmLoading={saving}
        title={
          <span style={{ color: 'var(--accent)', fontFamily: 'var(--mono)' }}>
            {modal === 'create' ? '新建普通管理员' : `修改密码 · ${editTarget?.username}`}
          </span>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 16 }}>
          {modal === 'create' && (
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 6 }}>用户名（至少3个字符）</div>
              <Input
                placeholder="请输入用户名"
                value={formUsername}
                onChange={e => setFormUsername(e.target.value)}
              />
            </div>
          )}
          <div>
            <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 6 }}>
              {modal === 'create' ? '初始密码（至少6位）' : '新密码（至少6位）'}
            </div>
            <Input.Password
              placeholder="请输入密码"
              value={formPassword}
              onChange={e => setFormPassword(e.target.value)}
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}
