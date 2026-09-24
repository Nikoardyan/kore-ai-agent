const API_BASE_URL = 'http://localhost:8000'

async function parseResponse(response) {
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
        throw new Error(data.detail || 'Request failed')
    }
    return data
}

function normalizeAuth(data) {
    return {
        token: data.token,
        user: {
            employeeId: data.user.employee_id,
            displayName: data.user.display_name || ''
        }
    }
}

export async function fetchHealth() {
    const response = await fetch(`${API_BASE_URL}/health`)
    return await parseResponse(response)
}

export async function registerEmployee({ employeeId, displayName, password }) {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            employee_id: employeeId,
            display_name: displayName || null,
            password
        })
    })
    return normalizeAuth(await parseResponse(response))
}

export async function loginEmployee({ employeeId, password }) {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            employee_id: employeeId,
            password
        })
    })
    return normalizeAuth(await parseResponse(response))
}

export async function fetchAuthSession(token) {
    const response = await fetch(`${API_BASE_URL}/auth/session`, {
        headers: { Authorization: `Bearer ${token}` }
    })
    return normalizeAuth(await parseResponse(response))
}

export async function sendMessage(message, userName, recentMessages = [], employeeId = null, token = '') {
    const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
            message,
            user_name: userName || null,
            employee_id: employeeId || null,
            recent_messages: recentMessages
        })
    })
    return await parseResponse(response)
}
