import React, { useState } from 'react'
import { Input, Button, message, Divider } from 'antd'
import { UserOutlined, LockOutlined, SafetyOutlined, EyeInvisibleOutlined, EyeTwoTone } from '@ant-design/icons'
import { login, resetPassword } from '../api.js'

export default function Login({ onLogin }) {
  const [mode, setMode]       = useState('login')   // 'login' | 'reset'
  const [loading, setLoading] = useState(false)

  // 登录表单
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  // 重置密码表单
  const [answer1, setAnswer1]       = useState('')
  const [answer2, setAnswer2]       = useState('')
  const [newPwd, setNewPwd]         = useState('')
  const [newPwd2, setNewPwd2]       = useState('')

  const handleLogin = async () => {
    if (!username.trim() || !password.trim())
      return message.warning('请输入用户名和密码')
    setLoading(true)
    try {
      const { data } = await login(username.trim(), password.trim())
      if (data.success) {
        localStorage.setItem('token', data.token)
        localStorage.setItem('user', JSON.stringify(data.user))
        message.success(`欢迎，${data.user.username}！`)
        onLogin(data.user)
      } else {
        message.error(data.error || '登录失败')
      }
    } catch (e) {
      message.error(e?.response?.data?.error || '网络错误，请检查后端是否启动')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = async () => {
    if (!answer1.trim() || !answer2.trim() || !newPwd.trim())
      return message.warning('请填写所有字段')
    if (newPwd !== newPwd2)
      return message.error('两次输入的新密码不一致')
    if (newPwd.length < 6)
      return message.error('新密码至少6位')
    setLoading(true)
    try {
      const { data } = await resetPassword(answer1.trim(), answer2.trim(), newPwd.trim())
      if (data.success) {
        message.success('密码重置成功！请用新密码登录')
        setMode('login')
        setAnswer1(''); setAnswer2(''); setNewPwd(''); setNewPwd2('')
      } else {
        message.error(data.error || '重置失败')
      }
    } catch (e) {
      message.error(e?.response?.data?.error || '重置失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg-base)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      {/* 背景装饰网格 */}
      <div style={{
        position: 'fixed', inset: 0, zIndex: 0,
        backgroundImage: 'linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px)',
        backgroundSize: '60px 60px',
        opacity: 0.4,
      }} />

      <div style={{
        position: 'relative', zIndex: 1,
        width: 420,
        background: 'var(--bg-panel)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '40px 40px 32px',
        boxShadow: '0 0 60px rgba(0,212,255,.08)',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 56, height: 56, borderRadius: '50%',
            background: 'var(--accent-glow)',
            border: '2px solid var(--accent-dim)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px',
          }}>
            <SafetyOutlined style={{ fontSize: 26, color: 'var(--accent)' }} />
          </div>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-1)', letterSpacing: 1 }}>
            智能监控系统
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-3)', fontFamily: 'var(--mono)', marginTop: 4 }}>
            VIDEO RETRIEVAL SYSTEM
          </div>
        </div>

        {/* 角标装饰 */}
        {[{t:'top',l:'left'},{t:'top',l:'right'},{t:'bottom',l:'left'},{t:'bottom',l:'right'}].map(({t,l},i)=>(
          <div key={i} style={{
            position:'absolute',
            [t]: 12, [l]: 12,
            width: 14, height: 14,
            borderTop:    t==='top'    ? '2px solid var(--accent-dim)' : 'none',
            borderBottom: t==='bottom' ? '2px solid var(--accent-dim)' : 'none',
            borderLeft:   l==='left'   ? '2px solid var(--accent-dim)' : 'none',
            borderRight:  l==='right'  ? '2px solid var(--accent-dim)' : 'none',
          }} />
        ))}

        {/* ── 登录模式 ── */}
        {mode === 'login' && (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 6 }}>用户名</div>
                <Input
                  size="large"
                  prefix={<UserOutlined style={{ color: 'var(--text-3)' }} />}
                  placeholder="请输入用户名"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  onPressEnter={handleLogin}
                />
              </div>
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 6 }}>密码</div>
                <Input.Password
                  size="large"
                  prefix={<LockOutlined style={{ color: 'var(--text-3)' }} />}
                  placeholder="请输入密码"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  onPressEnter={handleLogin}
                  iconRender={v => v ? <EyeTwoTone /> : <EyeInvisibleOutlined />}
                />
              </div>
            </div>

            <Button
              type="primary" block size="large"
              loading={loading} onClick={handleLogin}
              style={{ marginTop: 24, height: 44, fontSize: 15, fontWeight: 600 }}
            >
              登 录
            </Button>

            <div style={{ textAlign: 'center', marginTop: 16 }}>
              <span
                onClick={() => setMode('reset')}
                style={{ fontSize: 13, color: 'var(--text-3)', cursor: 'pointer' }}
                onMouseEnter={e => e.target.style.color = 'var(--accent)'}
                onMouseLeave={e => e.target.style.color = 'var(--text-3)'}
              >
                忘记密码？通过密保重置
              </span>
            </div>
          </>
        )}

        {/* ── 重置密码模式 ── */}
        {mode === 'reset' && (
          <>
            <div style={{
              background: 'var(--bg-base)',
              border: '1px solid var(--border)',
              borderRadius: 8, padding: '12px 16px', marginBottom: 20,
              fontSize: 12, color: 'var(--text-3)', lineHeight: 1.8,
            }}>
              ⚠️ 仅限超级管理员重置密码，请回答以下密保问题：
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-2)', marginBottom: 6 }}>
                  密保问题1：您父亲的名字是什么？
                </div>
                <Input
                  placeholder="请输入答案"
                  value={answer1}
                  onChange={e => setAnswer1(e.target.value)}
                />
              </div>
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-2)', marginBottom: 6 }}>
                  密保问题2：您母亲的名字是什么？
                </div>
                <Input
                  placeholder="请输入答案"
                  value={answer2}
                  onChange={e => setAnswer2(e.target.value)}
                />
              </div>
              <Divider style={{ borderColor: 'var(--border)', margin: '4px 0' }} />
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 6 }}>新密码（至少6位）</div>
                <Input.Password
                  placeholder="请输入新密码"
                  value={newPwd}
                  onChange={e => setNewPwd(e.target.value)}
                />
              </div>
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 6 }}>确认新密码</div>
                <Input.Password
                  placeholder="再次输入新密码"
                  value={newPwd2}
                  onChange={e => setNewPwd2(e.target.value)}
                  onPressEnter={handleReset}
                />
              </div>
            </div>

            <Button
              type="primary" block size="large"
              loading={loading} onClick={handleReset}
              style={{ marginTop: 20, height: 44 }}
            >
              重置密码
            </Button>
            <Button
              block size="large"
              onClick={() => setMode('login')}
              style={{ marginTop: 10, borderColor: 'var(--border)', color: 'var(--text-2)' }}
            >
              返回登录
            </Button>
          </>
        )}

        <div style={{ marginTop: 24, textAlign: 'center', fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>
          © 2026 视频人物检索系统 · 赵栓
        </div>
      </div>
    </div>
  )
}
