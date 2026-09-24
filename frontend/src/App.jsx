import { useEffect, useMemo, useRef, useState } from 'react'
import { fetchAuthSession, loginEmployee, registerEmployee, sendMessage } from './backendClient'
import './App.css'

const quickPrompts = [
  'Audit Pipeline CI/CD Kubernetes',
  'Refactoring API Gateway Go',
  'Investigasi tiket email & SLA'
]

const executionModes = [
  { id: 'autonomous', label: 'Full Autonomous Agent', hint: 'Mengeksekusi tanpa konfirmasi' },
  { id: 'copilot', label: 'Co-Pilot Mode', hint: 'Menyarankan, menunggu persetujuan' },
  { id: 'readonly', label: 'Read Only', hint: 'Hanya observasi & analisis' }
]

const STORAGE_KEY = 'kore-ai-chat-state-v5'
const LEGACY_STORAGE_KEY = 'nexus-core-chat-state-v5'
const STORAGE_VERSION = 5
const AUTH_TOKEN_KEY = 'kore-ai-session-token-v1'
const defaultChatHistory = [{ id: 1, title: 'Percakapan Baru' }]
const defaultMessagesByChat = { 1: [] }

function createLogoMark(label = 'K') {
  return (
    <span className="logo-mark" aria-hidden="true">
      <span />
      <span />
      <span />
      <span />
      <b>{label}</b>
    </span>
  )
}

/* ---------- Ikon provider (SVG inline, tanpa dependensi) ---------- */

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="currentColor" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="currentColor" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="currentColor" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="currentColor" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  )
}

function GithubIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  )
}

function inferSourceFromContent(content, source) {
  const normalizedSource = (source || '').toLowerCase()
  const normalizedContent = (content || '').toLowerCase()

  if (
    normalizedSource.includes('sqlite') ||
    normalizedSource.includes('database') ||
    normalizedContent.includes('data cuti dari database') ||
    normalizedContent.includes('data pegawai dari database') ||
    normalizedContent.includes('tiket dari database')
  ) {
    return source && source !== 'Unknown source' ? source : 'SQLite database'
  }

  if (
    normalizedSource.includes('conversation') ||
    normalizedSource.includes('problem solving') ||
    normalizedContent.includes('langkah solusi')
  ) {
    return source && source !== 'Unknown source' ? source : 'Problem solving'
  }

  return source || 'Unknown source'
}

function normalizeStoredMessage(message) {
  if (!message || typeof message !== 'object') {
    return null
  }

  if (message.role === 'user') {
    return {
      role: 'user',
      content: message.content || '',
      time: message.time || 'Tersimpan'
    }
  }

  return {
    role: 'ai',
    content: message.content || '',
    source: inferSourceFromContent(message.content, message.source),
    toolRun: Boolean(message.toolRun),
    agentSteps: Array.isArray(message.agentSteps) ? message.agentSteps : [],
    time: message.time || 'Tersimpan',
    liked: Boolean(message.liked),
    flagged: Boolean(message.flagged),
    streaming: false
  }
}

function normalizeMessagesByChat(messagesByChat) {
  if (!messagesByChat || typeof messagesByChat !== 'object') {
    return defaultMessagesByChat
  }

  return Object.fromEntries(
    Object.entries(messagesByChat).map(([chatId, messages]) => [
      chatId,
      Array.isArray(messages)
        ? messages.map(normalizeStoredMessage).filter(Boolean)
        : []
    ])
  )
}

function loadSavedState() {
  try {
    const rawState =
      window.localStorage.getItem(STORAGE_KEY) ||
      window.localStorage.getItem(LEGACY_STORAGE_KEY)
    if (!rawState) {
      return null
    }

    const savedState = JSON.parse(rawState)
    const chatHistory = Array.isArray(savedState.chatHistory) && savedState.chatHistory.length > 0
      ? savedState.chatHistory
      : defaultChatHistory

    return {
      chatHistory,
      messagesByChat: normalizeMessagesByChat(savedState.messagesByChat),
      activeChatId: savedState.activeChatId || chatHistory[0].id,
      input: savedState.input || '',
      userName: savedState.userName || '',
      mode: savedState.mode || 'autonomous',
      collapsed: Boolean(savedState.collapsed)
    }
  } catch {
    return null
  }
}

function extractUserName(message) {
  const lowerMessage = message.toLowerCase()
  if (
    lowerMessage.includes('nama saya siapa') ||
    lowerMessage.includes('nama aku siapa') ||
    lowerMessage.includes('namaku siapa')
  ) {
    return ''
  }

  const patterns = [
    /\b(?:nama saya|nama aku|nama gue|nama gua|namaku|panggil saya|panggil aku|panggil gue|panggil gua)\s+(?:adalah\s+)?([A-Za-z][A-Za-z\s]{1,40})/i,
    /\b(?:i am|my name is|call me)\s+([A-Za-z][A-Za-z\s]{1,40})/i
  ]

  for (const pattern of patterns) {
    const match = message.match(pattern)
    if (!match) continue

    const name = match[1]
      .split(/[,.!?]/)[0]
      .replace(/\b(dan|ya|nih|dong|tolong|inget|ingat)\b.*$/i, '')
      .trim()

    if (name) {
      return name
        .split(/\s+/)
        .map(part => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
        .join(' ')
    }
  }

  return ''
}

function getResponseMeta(source, content = '') {
  const inferredSource = inferSourceFromContent(content, source)
  const normalizedSource = inferredSource.toLowerCase()
  const normalizedContent = (content || '').toLowerCase()

  if (
    normalizedSource.includes('sqlite') ||
    normalizedSource.includes('database') ||
    normalizedContent.includes('data cuti dari database') ||
    normalizedContent.includes('data pegawai dari database') ||
    normalizedContent.includes('tiket dari database')
  ) {
    return {
      mode: 'Database Query',
      status: 'Database lookup completed',
      checks: ['Membaca SQLite database', 'Mengambil baris data yang cocok']
    }
  }

  if (normalizedSource.includes('conversation') || normalizedSource.includes('problem solving')) {
    return {
      mode: 'Conversation Mode',
      status: 'Conversation response completed',
      checks: ['Membaca konteks percakapan', 'Menyusun jawaban percakapan']
    }
  }

  return {
    mode: 'PDF Retrieval',
    status: 'PDF lookup completed',
    checks: ['Membaca PDF knowledge base', 'Menyusun jawaban berbasis sumber aktif']
  }
}

function formatTranscript(chatTitle, messages) {
  const lines = messages.map(
    message => `${message.role === 'user' ? 'Anda' : 'KORE AI'}: ${message.content}`
  )
  return `${chatTitle}\n\n${lines.join('\n\n')}`
}

function App() {
  const savedState = useMemo(() => loadSavedState(), [])
  const [authToken, setAuthToken] = useState(() => window.localStorage.getItem(AUTH_TOKEN_KEY) || '')
  const [currentUser, setCurrentUser] = useState(null)
  const [authChecking, setAuthChecking] = useState(Boolean(window.localStorage.getItem(AUTH_TOKEN_KEY)))
  const [authMode, setAuthMode] = useState('login')
  const [authSubmitting, setAuthSubmitting] = useState(false)
  const [authForm, setAuthForm] = useState({
    employeeId: '',
    displayName: '',
    password: '',
    confirmPassword: ''
  })
  const [authError, setAuthError] = useState('')
  const [input, setInput] = useState(savedState?.input || '')
  const [userName, setUserName] = useState(savedState?.userName || '')
  const [loadingChatId, setLoadingChatId] = useState(null)
  const [chatHistory, setChatHistory] = useState(savedState?.chatHistory || defaultChatHistory)
  const [messagesByChat, setMessagesByChat] = useState(savedState?.messagesByChat || defaultMessagesByChat)
  const [activeChatId, setActiveChatId] = useState(savedState?.activeChatId || 1)
  const [isToolPanelOpen, setIsToolPanelOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(savedState?.collapsed || false)
  const [searchQuery, setSearchQuery] = useState('')
  const [mode, setMode] = useState(savedState?.mode || 'autonomous')
  const [isModeOpen, setIsModeOpen] = useState(false)
  const [connectionStatus, setConnectionStatus] = useState('idle')
  const [editingChatId, setEditingChatId] = useState(null)
  const [editingTitle, setEditingTitle] = useState('')
  const [toast, setToast] = useState(null)
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)
  const toastTimerRef = useRef(null)

  const messages = messagesByChat[activeChatId] || []
  const isLoading = loadingChatId === activeChatId
  const workspaceName = currentUser?.displayName || currentUser?.employeeId || 'Engineer Workspace'

  const activeChat = useMemo(
    () => chatHistory.find(chat => chat.id === activeChatId),
    [activeChatId, chatHistory]
  )

  const selectedMode = executionModes.find(item => item.id === mode) || executionModes[0]

  const filteredHistory = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    if (!query) return chatHistory
    return chatHistory.filter(chat => chat.title.toLowerCase().includes(query))
  }, [chatHistory, searchQuery])

  const filteredPrompts = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    if (!query) return quickPrompts
    return quickPrompts.filter(prompt => prompt.toLowerCase().includes(query))
  }, [searchQuery])

  useEffect(() => {
    setMessagesByChat(prev => normalizeMessagesByChat(prev))
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading, activeChatId])

  useEffect(() => {
    if (!chatHistory.some(chat => chat.id === activeChatId)) {
      setActiveChatId(chatHistory[0]?.id || 1)
    }
  }, [activeChatId, chatHistory])

  useEffect(() => {
    if (!textareaRef.current) return
    textareaRef.current.style.height = 'auto'
    textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`
  }, [input])

  useEffect(() => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        chatHistory,
        messagesByChat: normalizeMessagesByChat(messagesByChat),
        activeChatId,
        input,
        userName,
        mode,
        collapsed,
        storageVersion: STORAGE_VERSION
      })
    )
  }, [chatHistory, messagesByChat, activeChatId, input, userName, mode, collapsed])

  useEffect(() => () => clearTimeout(toastTimerRef.current), [])

  useEffect(() => {
    if (!authToken) {
      setAuthChecking(false)
      return undefined
    }

    let cancelled = false
    setAuthChecking(true)
    fetchAuthSession(authToken)
      .then(({ token, user }) => {
        if (cancelled) return
        window.localStorage.setItem(AUTH_TOKEN_KEY, token)
        setAuthToken(token)
        setCurrentUser(user)
        setUserName(user.displayName || user.employeeId)
      })
      .catch(() => {
        if (cancelled) return
        window.localStorage.removeItem(AUTH_TOKEN_KEY)
        setAuthToken('')
        setCurrentUser(null)
      })
      .finally(() => {
        if (!cancelled) setAuthChecking(false)
      })

    return () => {
      cancelled = true
    }
  }, [authToken])

  const updateAuthForm = (field, value) => {
    setAuthError('')
    setAuthForm(prev => ({ ...prev, [field]: value }))
  }

  const switchAuthMode = (modeName) => {
    setAuthMode(modeName)
    setAuthError('')
  }

  const showToast = (text) => {
    clearTimeout(toastTimerRef.current)
    setToast({ id: Date.now(), text })
    toastTimerRef.current = setTimeout(() => setToast(null), 2600)
  }

  const handleLogin = async (event) => {
    event.preventDefault()
    const employeeId = authForm.employeeId.trim()
    const password = authForm.password

    if (!employeeId || !password) {
      setAuthError('Nomor ID karyawan dan kata sandi wajib diisi.')
      return
    }

    setAuthSubmitting(true)
    try {
      const { token, user } = await loginEmployee({ employeeId, password })
      window.localStorage.setItem(AUTH_TOKEN_KEY, token)
      setAuthToken(token)
      setCurrentUser(user)
      setUserName(user.displayName || user.employeeId)
      setAuthForm({ employeeId: '', displayName: '', password: '', confirmPassword: '' })
      showToast(`Masuk sebagai ${user.employeeId}`)
    } catch (error) {
      setAuthError(error.message || 'Gagal masuk.')
    } finally {
      setAuthSubmitting(false)
    }
  }

  const handleRegister = async (event) => {
    event.preventDefault()
    const employeeId = authForm.employeeId.trim()
    const displayName = authForm.displayName.trim()
    const password = authForm.password
    const confirmPassword = authForm.confirmPassword

    if (!employeeId || !password || !confirmPassword) {
      setAuthError('ID karyawan, kata sandi, dan konfirmasi sandi wajib diisi.')
      return
    }

    if (password.length < 6) {
      setAuthError('Kata sandi minimal 6 karakter.')
      return
    }

    if (password !== confirmPassword) {
      setAuthError('Konfirmasi sandi belum sama.')
      return
    }

    setAuthSubmitting(true)
    try {
      const { token, user } = await registerEmployee({ employeeId, displayName, password })
      window.localStorage.setItem(AUTH_TOKEN_KEY, token)
      setAuthToken(token)
      setCurrentUser(user)
      setUserName(user.displayName || user.employeeId)
      setAuthForm({ employeeId: '', displayName: '', password: '', confirmPassword: '' })
      showToast('Akun KORE AI dibuat')
    } catch (error) {
      setAuthError(error.message || 'Gagal daftar akun.')
    } finally {
      setAuthSubmitting(false)
    }
  }

  const handleLogout = () => {
    window.localStorage.removeItem(AUTH_TOKEN_KEY)
    setAuthToken('')
    setCurrentUser(null)
    setAuthMode('login')
    setAuthForm({ employeeId: '', displayName: '', password: '', confirmPassword: '' })
    setAuthError('')
    showToast('Keluar dari workspace')
  }

  const appendMessageToChat = (chatId, message) => {
    setMessagesByChat(prev => ({
      ...prev,
      [chatId]: [...(prev[chatId] || []), message]
    }))
  }

  const updateMessageAt = (chatId, index, updater) => {
    setMessagesByChat(prev => ({
      ...prev,
      [chatId]: (prev[chatId] || []).map((message, messageIndex) =>
        messageIndex === index ? updater(message) : message
      )
    }))
  }

  const updateCurrentChatTitle = (chatId, message) => {
    if ((messagesByChat[chatId] || []).length > 0) return

    setChatHistory(prev =>
      prev.map(chat =>
        chat.id === chatId
          ? { ...chat, title: message.slice(0, 44) + (message.length > 44 ? '...' : '') }
          : chat
      )
    )
  }

  const handleSend = async (message = input) => {
    const trimmedMessage = message.trim()
    if (!trimmedMessage || loadingChatId) return

    const chatId = activeChatId
    const detectedName = extractUserName(trimmedMessage)
    const rememberedName = detectedName || userName
    const recentMessages = (messagesByChat[chatId] || [])
      .slice(-8)
      .map(messageItem => ({
        role: messageItem.role,
        content: messageItem.content,
        source: messageItem.source || ''
      }))

    if (detectedName) {
      setUserName(detectedName)
    }

    appendMessageToChat(chatId, {
      role: 'user',
      content: trimmedMessage,
      time: 'Baru Saja'
    })
    setInput('')
    setIsToolPanelOpen(false)
    setLoadingChatId(chatId)
    updateCurrentChatTitle(chatId, trimmedMessage)

    try {
      const response = await sendMessage(
        trimmedMessage,
        rememberedName,
        recentMessages,
        currentUser?.employeeId,
        authToken
      )
      const responseMeta = getResponseMeta(response.source)
      setConnectionStatus('online')
      appendMessageToChat(chatId, {
        role: 'ai',
        mode: responseMeta.mode,
        status: responseMeta.status,
        checks: responseMeta.checks,
        content: response.reply,
        source: response.source,
        agentSteps: Array.isArray(response.agent_steps) ? response.agent_steps : [],
        toolRun: Array.isArray(response.agent_steps) && response.agent_steps.length > 0,
        time: 'Baru Saja',
        liked: false,
        flagged: false,
        streaming: true
      })
    } catch {
      setConnectionStatus('offline')
      appendMessageToChat(chatId, {
        role: 'ai',
        mode: 'System Notice',
        status: 'Backend connection failed',
        checks: ['Memeriksa endpoint http://localhost:8000/chat'],
        content: 'Maaf, server belum merespons. Pastikan backend FastAPI berjalan di http://localhost:8000.',
        source: 'System status',
        time: 'Baru Saja',
        liked: false,
        flagged: false,
        streaming: true
      })
    } finally {
      setLoadingChatId(null)
    }
  }

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }

  const handleNewChat = () => {
    const newId = Date.now()
    setChatHistory(prev => [{ id: newId, title: 'Percakapan Baru' }, ...prev])
    setMessagesByChat(prev => ({ ...prev, [newId]: [] }))
    setActiveChatId(newId)
    setInput('')
    setIsToolPanelOpen(false)
  }

  const handleHistoryClick = (chatId) => {
    if (editingChatId === chatId) return
    setActiveChatId(chatId)
    setInput('')
    setIsToolPanelOpen(false)
  }

  const handleToolPrompt = (prompt) => {
    setInput(prompt)
    setIsToolPanelOpen(false)
  }

  const handleStartRename = (chat, event) => {
    event.stopPropagation()
    setEditingChatId(chat.id)
    setEditingTitle(chat.title)
  }

  const commitRename = () => {
    const trimmedTitle = editingTitle.trim()
    if (trimmedTitle) {
      setChatHistory(prev =>
        prev.map(chat => (chat.id === editingChatId ? { ...chat, title: trimmedTitle } : chat))
      )
    }
    setEditingChatId(null)
  }

  const handleDeleteChat = (chatId, event) => {
    event.stopPropagation()
    setChatHistory(prev => {
      const next = prev.filter(chat => chat.id !== chatId)
      return next.length > 0 ? next : [{ id: Date.now(), title: 'Percakapan Baru' }]
    })
    setMessagesByChat(prev => {
      const next = { ...prev }
      delete next[chatId]
      return next
    })
    showToast('Percakapan dihapus')
  }

  const handleShareSession = async () => {
    if (!messages.length) {
      showToast('Belum ada percakapan untuk dibagikan')
      return
    }
    const text = formatTranscript(activeChat?.title || 'Percakapan', messages)
    try {
      await navigator.clipboard.writeText(text)
      showToast('Sesi disalin ke clipboard')
    } catch {
      showToast('Gagal menyalin sesi')
    }
  }

  const handleDownloadSession = () => {
    if (!messages.length) {
      showToast('Belum ada percakapan untuk diunduh')
      return
    }
    const text = formatTranscript(activeChat?.title || 'Percakapan', messages)
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${(activeChat?.title || 'sesi').replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.txt`
    link.click()
    URL.revokeObjectURL(url)
    showToast('Sesi diunduh')
  }

  const handleCopyMessage = async (content) => {
    try {
      await navigator.clipboard.writeText(content)
      showToast('Pesan disalin')
    } catch {
      showToast('Gagal menyalin pesan')
    }
  }

  const handleRegenerate = (chatId, index) => {
    const chatMessages = messagesByChat[chatId] || []
    let precedingUserContent = null
    for (let i = index - 1; i >= 0; i -= 1) {
      if (chatMessages[i].role === 'user') {
        precedingUserContent = chatMessages[i].content
        break
      }
    }
    if (precedingUserContent) {
      handleSend(precedingUserContent)
    }
  }

  const handleToggleLike = (chatId, index) => {
    updateMessageAt(chatId, index, message => ({
      ...message,
      liked: !message.liked,
      flagged: message.liked ? message.flagged : false
    }))
  }

  const handleToggleFlag = (chatId, index) => {
    updateMessageAt(chatId, index, message => ({
      ...message,
      flagged: !message.flagged,
      liked: message.flagged ? message.liked : false
    }))
    if (!messages[index]?.flagged) {
      showToast('Respons ditandai untuk ditinjau')
    }
  }

  const handleDoneStreaming = (chatId, index) => {
    updateMessageAt(chatId, index, message => ({ ...message, streaming: false }))
  }

  if (authChecking) {
    return (
      <div className="auth-page">
        <main className="auth-main auth-loading">
          {createLogoMark()}
          <p>Memeriksa sesi KORE AI...</p>
        </main>
      </div>
    )
  }

  if (!currentUser) {
    return (
      <>
        <AuthScreen
          mode={authMode}
          form={authForm}
          error={authError}
          submitting={authSubmitting}
          onChange={updateAuthForm}
          onModeChange={switchAuthMode}
          onLogin={handleLogin}
          onRegister={handleRegister}
        />
        {toast && (
          <div className="toast" key={toast.id} role="status">
            {toast.text}
          </div>
        )}
      </>
    )
  }

  return (
    <div className="agent-shell">
      <aside className={`agent-sidebar${collapsed ? ' collapsed' : ''}`} aria-label="Navigasi KORE AI">
        <div className="sidebar-brand">
          {createLogoMark()}
          <div className="brand-copy">
            <h1>KORE AI</h1>
            <span>KORE AUTONOMOUS V2.5</span>
          </div>
          <button
            className="icon-button ghost"
            type="button"
            aria-label={collapsed ? 'Perluas sidebar' : 'Ciutkan sidebar'}
            onClick={() => setCollapsed(prev => !prev)}
          >
            {collapsed ? '»' : '«'}
          </button>
        </div>

        <button className="primary-action" type="button" onClick={handleNewChat}>
          <span aria-hidden="true">+</span>
          <span className="label-text">Percakapan Baru</span>
          <kbd>Ctrl K</kbd>
        </button>

        <label className="search-box">
          <span aria-hidden="true">⌕</span>
          <input
            placeholder="Cari sesi & tugas agent..."
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
          />
        </label>

        <section className="mode-panel" aria-label="Mode eksekusi">
          <p className="label-text">MODE EKSEKUSI:</p>
          <div className="mode-select">
            <button
              type="button"
              aria-expanded={isModeOpen}
              onClick={() => setIsModeOpen(prev => !prev)}
            >
              <span className="live-dot" aria-hidden="true" />
              <span className="label-text">{selectedMode.label}</span>
              <span aria-hidden="true" className={`chevron${isModeOpen ? ' open' : ''}`}>⌄</span>
            </button>
            {isModeOpen && (
              <div className="mode-dropdown">
                {executionModes.map(item => (
                  <button
                    key={item.id}
                    type="button"
                    className={item.id === mode ? 'active' : ''}
                    onClick={() => {
                      setMode(item.id)
                      setIsModeOpen(false)
                      showToast(`Mode diubah ke ${item.label}`)
                    }}
                  >
                    <span>{item.label}</span>
                    <small>{item.hint}</small>
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>

        <nav className="session-list">
          <p className="label-text">HARI INI</p>
          {filteredHistory.map(chat => (
            <div
              key={chat.id}
              className={`session-item${chat.id === activeChatId ? ' active' : ''}`}
              onClick={() => handleHistoryClick(chat.id)}
            >
              <span aria-hidden="true" className="session-icon">▤</span>
              {editingChatId === chat.id ? (
                <input
                  className="session-rename-input"
                  value={editingTitle}
                  autoFocus
                  onChange={(event) => setEditingTitle(event.target.value)}
                  onBlur={commitRename}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') commitRename()
                    if (event.key === 'Escape') setEditingChatId(null)
                  }}
                  onClick={(event) => event.stopPropagation()}
                />
              ) : (
                <span className="session-title" onDoubleClick={(event) => handleStartRename(chat, event)}>
                  {chat.title}
                </span>
              )}
              <button
                type="button"
                className="session-delete"
                aria-label="Hapus percakapan"
                onClick={(event) => handleDeleteChat(chat.id, event)}
              >
                ×
              </button>
            </div>
          ))}
          {filteredHistory.length === 0 && <p className="empty-hint">Tidak ditemukan.</p>}

          <p className="label-text">7 HARI TERAKHIR</p>
          {filteredPrompts.map(prompt => (
            <button key={prompt} type="button" className="session-item quick" onClick={() => setInput(prompt)}>
              <span aria-hidden="true" className="session-icon">~</span>
              <span className="session-title">{prompt}</span>
            </button>
          ))}
        </nav>

        <div className="workspace-profile">
          <div className="profile-avatar">{currentUser.employeeId.slice(0, 2).toUpperCase()}</div>
          <div className="profile-copy">
            <strong>{workspaceName}</strong>
            <span>{currentUser.employeeId}</span>
          </div>
          <button className="icon-button ghost" type="button" aria-label="Keluar" onClick={handleLogout}>↪</button>
        </div>
      </aside>

      <main className="agent-main">
        <header className="agent-topbar">
          <div className="topbar-title">
            <h2>{activeChat?.title || 'Percakapan Baru'}</h2>
            <span className="engine-badge">
              <i /> KORE Reasoning Engine 4.0
            </span>
            <span className={`status-pill ${connectionStatus}`}>
              <i className="live-dot" />
              {connectionStatus === 'online' ? 'Live' : connectionStatus === 'offline' ? 'Terputus' : 'Siaga'}
            </span>
          </div>
          <div className="topbar-actions">
            <button className="utility-button" type="button" onClick={handleShareSession}>
              Bagikan Sesi
            </button>
            <button className="icon-button" type="button" aria-label="Unduh sesi" onClick={handleDownloadSession}>
              ⬇
            </button>
          </div>
        </header>

        <section className="conversation-panel" aria-label="Percakapan KORE AI">
          {messages.length > 0 && (
            <div className="date-divider">
              <span>HARI INI</span>
            </div>
          )}

          {messages.length === 0 ? (
            <div className="empty-state">
              <div className="empty-orb">{createLogoMark()}</div>
              <h2>Selamat pagi, {workspaceName}.</h2>
              <p>Pilih prompt dari sidebar atau ketik instruksi operasional di bawah.</p>
            </div>
          ) : (
            <div className="messages-stack">
              {messages.map((message, index) => (
                <Message
                  key={`${message.role}-${index}`}
                  message={message}
                  chatId={activeChatId}
                  index={index}
                  onCopy={handleCopyMessage}
                  onRegenerate={handleRegenerate}
                  onToggleLike={handleToggleLike}
                  onToggleFlag={handleToggleFlag}
                  onDoneStreaming={handleDoneStreaming}
                />
              ))}

              {isLoading && (
                <article className="message-row ai">
                  <div className="agent-icon" aria-hidden="true">K</div>
                  <div className="message-body">
                    <div className="message-meta">
                      <strong>KORE AI</strong>
                      <span className="mode-badge">Autonomous Executing</span>
                      <span>Baru Saja</span>
                    </div>
                    <div className="reasoning-card compact">
                      <span className="typing-dots" aria-hidden="true">
                        <i /><i /><i />
                      </span>
                      Memproses permintaan dan memilih sumber data...
                    </div>
                  </div>
                </article>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </section>

        <footer className="agent-composer">
          <div className="composer-shell">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Tanyakan apapun atau tugaskan KORE AI untuk mengeksekusi workflow..."
              disabled={isLoading}
              rows={1}
            />
            <div className="composer-bottom">
              <div className="composer-tools">
                <button
                  type="button"
                  aria-label="Buka aksi cepat"
                  aria-expanded={isToolPanelOpen}
                  onClick={() => setIsToolPanelOpen(prev => !prev)}
                >
                  +
                </button>
                <button type="button" onClick={() => setIsToolPanelOpen(prev => !prev)}>Tools Aktif (3)</button>
                <button type="button" onClick={() => handleToolPrompt('Cari informasi operasional terbaru dari Web Ops.')}>Web Ops</button>
              </div>
              <button
                className="send-button"
                type="button"
                aria-label="Kirim pesan"
                onClick={() => handleSend()}
                disabled={!input.trim() || isLoading}
              >
                ➤
              </button>
            </div>

            {isToolPanelOpen && (
              <div className="quick-tool-panel">
                <p>Aksi cepat</p>
                {quickPrompts.map(prompt => (
                  <button key={prompt} type="button" onClick={() => handleToolPrompt(prompt)}>
                    {prompt}
                  </button>
                ))}
              </div>
            )}
          </div>
          <p>KORE AI dapat mengambil tindakan mandiri berdasarkan izin integrasi workspace Anda.</p>
        </footer>
      </main>

      {toast && (
        <div className="toast" key={toast.id} role="status">
          {toast.text}
        </div>
      )}
    </div>
  )
}

function AuthScreen({ mode, form, error, submitting, onChange, onModeChange, onLogin, onRegister }) {
  const isRegister = mode === 'register'

  return (
    <div className="auth-page">
      <header className="auth-topbar">
        <div className="auth-brand">
          {createLogoMark()}
          <strong>KORE AI</strong>
          <span>KORE AUTONOMOUS V2.5</span>
        </div>
        <nav className="auth-nav" aria-label="Navigasi autentikasi">
          <button type="button" className={isRegister ? 'active' : ''} onClick={() => onModeChange('register')}>
            Daftar Akun
          </button>
          <button type="button">Enterprise SSO</button>
          <button type="button">Dokumentasi</button>
        </nav>
        <div className="auth-actions">
          <span>Enterprise SSO Ready</span>
          <button type="button" onClick={() => onModeChange('login')}>Masuk</button>
        </div>
      </header>

      <main className="auth-main">
        <section className="auth-copy">
          <div className="eyebrow">Akses Otonom Instan • Enkripsi Workspace</div>
          <h1>{isRegister ? 'Mulai dengan KORE AI' : 'Selamat Datang Kembali'}</h1>
          <p>
            {isRegister
              ? 'Daftarkan ID karyawan dan kata sandi bebas untuk membuka workspace AI.'
              : 'Masuk memakai ID karyawan yang sudah terdaftar sebelum mengakses AI.'}
          </p>
        </section>

        <div className="auth-grid">
          <section className="auth-card" aria-label={isRegister ? 'Daftar akun KORE AI' : 'Masuk KORE AI'}>
            <div className="auth-provider-grid">
              <button type="button">
                <GoogleIcon />
                <span>{isRegister ? 'Daftar via Google' : 'Masuk via Google'}</span>
              </button>
              <button type="button">
                <GithubIcon />
                <span>{isRegister ? 'Daftar via GitHub' : 'Masuk via GitHub'}</span>
              </button>
            </div>

            <div className="auth-divider">
              <span>{isRegister ? 'ATAU REGISTRASI LANGSUNG' : 'ATAU DENGAN EMAIL KERJA'}</span>
            </div>

            <form onSubmit={isRegister ? onRegister : onLogin}>
              <label>
                <span>NOMOR ID KARYAWAN</span>
                <input
                  value={form.employeeId}
                  onChange={(event) => onChange('employeeId', event.target.value)}
                  placeholder="Contoh: KORE-9021 atau 123456"
                  autoComplete="username"
                  disabled={submitting}
                />
              </label>

              {isRegister && (
                <label>
                  <span>NAMA LENGKAP / PANGGILAN</span>
                  <input
                    value={form.displayName}
                    onChange={(event) => onChange('displayName', event.target.value)}
                    placeholder="Opsional"
                    autoComplete="name"
                    disabled={submitting}
                  />
                </label>
              )}

              <label>
                <span>KATA SANDI</span>
                <input
                  value={form.password}
                  onChange={(event) => onChange('password', event.target.value)}
                  placeholder="Masukkan kata sandi bebas Anda"
                  type="password"
                  autoComplete={isRegister ? 'new-password' : 'current-password'}
                  disabled={submitting}
                />
              </label>

              {isRegister && (
                <label>
                  <span>KONFIRMASI SANDI</span>
                  <input
                    value={form.confirmPassword}
                    onChange={(event) => onChange('confirmPassword', event.target.value)}
                    placeholder="Ketik ulang kata sandi"
                    type="password"
                    autoComplete="new-password"
                    disabled={submitting}
                  />
                </label>
              )}

              {error && <p className="auth-error" role="alert">{error}</p>}

              <button className="auth-submit" type="submit" disabled={submitting}>
                {submitting
                  ? 'Memproses...'
                  : isRegister
                    ? 'Buat Akun KORE AI & Mulai'
                    : 'Masuk ke Workspace'} <span>→</span>
              </button>
            </form>

            <div className="auth-switch">
              {isRegister ? 'Sudah memiliki akun?' : 'Belum memiliki akun KORE AI?'}
              <button type="button" onClick={() => onModeChange(isRegister ? 'login' : 'register')}>
                {isRegister ? 'Masuk ke sini' : 'Daftar sekarang gratis'}
              </button>
            </div>
          </section>

          <aside className="auth-telemetry" aria-label="Telemetry cluster KORE">
            <div className="telemetry-card">
              <div className="telemetry-head">
                <strong>Telemetry Cluster KORE</strong>
                <span>SYS-LIVE</span>
              </div>
              <div className="metric-grid">
                <div>
                  <span>CLUSTER</span>
                  <strong>3 Aktif</strong>
                  <small>us-east, eu, ap</small>
                </div>
                <div>
                  <span>UPTIME</span>
                  <strong>99.98%</strong>
                  <small>SLA Enterprise</small>
                </div>
                <div>
                  <span>KEAMANAN</span>
                  <strong>SOC2-II</strong>
                  <small>Encrypted-At-Rest</small>
                </div>
              </div>
              <div className="sparkline" aria-hidden="true">
                <i /><i /><i /><i /><i /><i /><i />
              </div>
              <div className="agent-pipeline">
                <b>Agent Planner V3</b>
                <span>Mengevaluasi graph dependensi dan auto-scaling node.</span>
              </div>
            </div>
          </aside>
        </div>
      </main>
    </div>
  )
}

function Message({ message, chatId, index, onCopy, onRegenerate, onToggleLike, onToggleFlag, onDoneStreaming }) {
  const isUser = message.role === 'user'
  const [displayLength, setDisplayLength] = useState(
    !isUser && message.streaming ? 0 : message.content.length
  )

  useEffect(() => {
    if (isUser || !message.streaming) return undefined

    const total = message.content.length
    let current = 0
    let timerId

    const step = () => {
      current = Math.min(total, current + Math.max(1, Math.round(total / 45)))
      setDisplayLength(current)
      if (current < total) {
        timerId = setTimeout(step, 14)
      } else {
        onDoneStreaming?.(chatId, index)
      }
    }

    timerId = setTimeout(step, 14)
    return () => clearTimeout(timerId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (isUser) {
    return (
      <article className="message-row user">
        <div className="user-bubble">{message.content}</div>
        <div className="user-avatar" aria-hidden="true">U</div>
        <time>{message.time} · Terkirim</time>
      </article>
    )
  }

  const shownContent = message.streaming ? message.content.slice(0, displayLength) : message.content
  const isStillStreaming = message.streaming && displayLength < message.content.length

  const inferredSource = inferSourceFromContent(message.content, message.source)
  const sources = inferredSource
    ? inferredSource.split(',').map(source => source.trim()).filter(Boolean)
    : []
  const displayMeta = getResponseMeta(inferredSource, message.content)
  const isSystemNotice = message.source === 'System status'
  const mode = isSystemNotice ? message.mode : displayMeta.mode
  const status = isSystemNotice ? message.status : displayMeta.status
  const checks = isSystemNotice ? message.checks : displayMeta.checks

  return (
    <article className="message-row ai">
      <div className="agent-icon" aria-hidden="true">K</div>
      <div className="message-body">
        <div className="message-meta">
          <strong>KORE AI</strong>
          {mode && <span className="mode-badge">{mode}</span>}
          <span>{message.time}</span>
        </div>

        {isSystemNotice && status && (
          <div className="reasoning-card">
            <div className="reasoning-head">
              <span>
                <i className="live-dot" />
                {status}
              </span>
            </div>
            {checks?.map((check, checkIndex) => (
              <p key={check}>
                <b>{checkIndex + 1}.</b> {check}
              </p>
            ))}
          </div>
        )}

        <div className="assistant-card">
          <p>
            {shownContent}
            {isStillStreaming && <span className="stream-cursor" aria-hidden="true" />}
          </p>
          {sources.length > 0 && !isStillStreaming && (
            <div className="source-row">
              <span>Sumber:</span>
              {sources.map(source => (
                <mark key={source}>{source}</mark>
              ))}
            </div>
          )}
        </div>

        <div className="feedback-row">
          <button type="button" onClick={() => onCopy(message.content)}>Salin</button>
          <button type="button" onClick={() => onRegenerate(chatId, index)}>Buat Ulang</button>
          <button
            type="button"
            className={message.liked ? 'active' : ''}
            onClick={() => onToggleLike(chatId, index)}
          >
            Like
          </button>
          <button
            type="button"
            className={message.flagged ? 'active flag' : ''}
            onClick={() => onToggleFlag(chatId, index)}
          >
            Flag
          </button>
          <span>Respons agent</span>
        </div>
      </div>
    </article>
  )
}

export default App