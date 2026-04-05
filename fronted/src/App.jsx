import React, { useState, useEffect } from 'react'
import { Routes, Route, NavLink, useLocation, Navigate } from 'react-router-dom'
import { ConfigProvider, theme, Dropdown, Avatar, message } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import {
  VideoCameraOutlined, SearchOutlined, PictureOutlined,
  DatabaseOutlined, EnvironmentOutlined, RadarChartOutlined,
  UserOutlined, CrownOutlined, LogoutOutlined, TeamOutlined,
  HistoryOutlined,
} from '@ant-design/icons'
import Monitor       from './pages/Monitor.jsx'
import TextSearch    from './pages/TextSearch.jsx'
import ImageSearch   from './pages/ImageSearch.jsx'
import DataManage    from './pages/DataManage.jsx'
import Trajectory    from './pages/Trajectory.jsx'
import Login         from './pages/Login.jsx'
import UserManage    from './pages/UserManage.jsx'
import SearchHistory from './pages/SearchHistory.jsx'
import { logout } from './api.js'

// ── 导航项（isSuperOnly=true 表示仅超管可见）──
const NAV = [
  { path: '/',           icon: <VideoCameraOutlined />,  label: '实时监控' },
  { path: '/text',       icon: <SearchOutlined />,       label: '文字搜图' },
  { path: '/image',      icon: <PictureOutlined />,      label: '以图搜图' },
  { path: '/data',       icon: <DatabaseOutlined />,     label: '数据管理' },
  { path: '/trajectory', icon: <EnvironmentOutlined />,  label: '时空轨迹' },
  { path: '/history',    icon: <HistoryOutlined />,      label: '搜索历史' },
  { path: '/users',      icon: <TeamOutlined />,         label: '用户管理', isSuperOnly: true },
]

export default function App() {
  const location = useLocation()
  const [time, setTime]   = useState(new Date())
  const [user, setUser]   = useState(() => {
    try { return JSON.parse(localStorage.getItem('user')) } catch { return null }
  })

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  const fmt = d => d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  })

  const handleLogin = (userInfo) => {
    setUser(userInfo)
  }

  const handleLogout = async () => {
    try { await logout() } catch {}
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setUser(null)
    message.success('已退出登录')
  }

  const isSuperuser = user?.role === 'superuser'

  // ── 未登录：显示登录页 ──
  if (!user) {
    return (
      <ConfigProvider locale={zhCN} theme={{
        algorithm: theme.darkAlgorithm,
        token: { colorPrimary: '#00d4ff', colorBgBase: '#080c14', borderRadius: 6,
                 fontFamily: "'Noto Sans SC', sans-serif" }
      }}>
        <Login onLogin={handleLogin} />
      </ConfigProvider>
    )
  }

  // 用户下拉菜单
  const userMenuItems = [
    {
      key: 'info',
      label: (
        <div style={{ padding: '4px 0' }}>
          <div style={{ fontWeight: 600, color: 'var(--text-1)' }}>{user.username}</div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>
            {isSuperuser ? '超级管理员' : '普通管理员'}
          </div>
        </div>
      ),
      disabled: true,
    },
    { type: 'divider' },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      danger: true,
      onClick: handleLogout,
    },
  ]

  return (
    <ConfigProvider locale={zhCN} theme={{
      algorithm: theme.darkAlgorithm,
      token: { colorPrimary: '#00d4ff', colorBgBase: '#080c14', borderRadius: 6,
               fontFamily: "'Noto Sans SC', sans-serif" }
    }}>
      <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>

        {/* ── 侧边栏 ── */}
        <aside style={{
          width: 220, flexShrink: 0,
          background: 'var(--bg-panel)',
          borderRight: '1px solid var(--border)',
          display: 'flex', flexDirection: 'column',
        }}>
          {/* Logo */}
          <div style={{ padding: '20px 20px 16px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <RadarChartOutlined style={{ fontSize: 22, color: 'var(--accent)' }} />
              <div>
                <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--text-1)', letterSpacing: 1 }}>
                  智能监控
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>
                  VIDEO RETRIEVAL
                </div>
              </div>
            </div>
          </div>

          {/* 导航 */}
          <nav style={{ flex: 1, padding: '12px 10px', overflow: 'auto' }}>
            {NAV.map(item => {
              // 超管专属页面，普通管理员不显示
              if (item.isSuperOnly && !isSuperuser) return null
              const active = location.pathname === item.path
              return (
                <NavLink key={item.path} to={item.path} style={{ textDecoration: 'none' }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '10px 12px', borderRadius: 6, marginBottom: 2,
                    background: active ? 'var(--accent-glow)' : 'transparent',
                    border: active ? '1px solid var(--accent-dim)' : '1px solid transparent',
                    color: active ? 'var(--accent)' : 'var(--text-2)',
                    transition: 'all .2s', cursor: 'pointer',
                  }}
                  onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'var(--bg-hover)' }}
                  onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent' }}
                  >
                    <span style={{ fontSize: 16 }}>{item.icon}</span>
                    <span style={{ fontSize: 13, fontWeight: active ? 600 : 400 }}>{item.label}</span>
                    {item.isSuperOnly && (
                      <CrownOutlined style={{ marginLeft: 'auto', fontSize: 11, color: '#ffd700', opacity: 0.7 }} />
                    )}
                    {active && !item.isSuperOnly && (
                      <div style={{
                        marginLeft: 'auto', width: 6, height: 6,
                        borderRadius: '50%', background: 'var(--accent)',
                      }} className="pulse" />
                    )}
                  </div>
                </NavLink>
              )
            })}
          </nav>

          {/* 底部：用户信息 + 时钟 */}
          <div style={{ borderTop: '1px solid var(--border)' }}>
            {/* 用户信息 */}
            <Dropdown menu={{ items: userMenuItems }} trigger={['click']} placement="topLeft">
              <div style={{
                padding: '12px 16px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 10,
                borderBottom: '1px solid var(--border)',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <Avatar
                  size={30}
                  style={{
                    background: isSuperuser ? 'linear-gradient(135deg,#ffd700,#ff8c00)' : 'var(--accent-glow)',
                    border: `1px solid ${isSuperuser ? '#ffd700' : 'var(--accent-dim)'}`,
                    flexShrink: 0,
                  }}
                  icon={isSuperuser ? <CrownOutlined /> : <UserOutlined />}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {user.username}
                  </div>
                  <div style={{ fontSize: 10, color: isSuperuser ? '#ffd700' : 'var(--text-3)', fontFamily: 'var(--mono)' }}>
                    {isSuperuser ? '超级管理员' : '普通管理员'}
                  </div>
                </div>
                <LogoutOutlined style={{ fontSize: 13, color: 'var(--text-3)' }} />
              </div>
            </Dropdown>

            {/* 时钟 */}
            <div style={{ padding: '10px 20px', fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-3)' }}>
              <div style={{ color: 'var(--green)', marginBottom: 2, fontSize: 10 }}>● 系统运行中</div>
              {fmt(time)}
            </div>
          </div>
        </aside>

        {/* ── 主内容区 ── */}
        <main style={{ flex: 1, overflow: 'auto', background: 'var(--bg-base)' }}>
          <Routes>
            <Route path="/"           element={<Monitor />} />
            <Route path="/text"       element={<TextSearch />} />
            <Route path="/image"      element={<ImageSearch />} />
            <Route path="/trajectory" element={<Trajectory />} />

            {/* 数据管理：传入权限标志 */}
            <Route path="/data" element={
              <DataManage isSuperuser={isSuperuser} />
            } />

            {/* 搜索历史 */}
            <Route path="/history" element={
              <SearchHistory isSuperuser={isSuperuser} />
            } />

            {/* 用户管理：仅超管可访问 */}
            <Route path="/users" element={
              isSuperuser ? <UserManage /> : <Navigate to="/" replace />
            } />
          </Routes>
        </main>
      </div>
    </ConfigProvider>
  )
}
