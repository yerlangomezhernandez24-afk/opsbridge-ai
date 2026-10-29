import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

const session = {
  user_id: '00000000-0000-4000-8000-000000000001',
  login_id: 'demo.requester',
  display_name: 'Demo Requester',
  role: 'requester',
  permissions: ['ticket:create'],
  csrf_token: 'csrf-test',
  expires_at: '2030-01-01T00:00:00Z',
}

const emptySummary = { data: { total: 0, by_status: [], by_priority: [], by_category: [], created_by_day: [] } }

function requestPath(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  return input instanceof URL ? input.toString() : input.url
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('OpsBridge application shell', () => {
  it('shows the secure login when there is no active session', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({ detail: 'Authentication required' }), { status: 401, headers: { 'Content-Type': 'application/problem+json' } }))))
    render(<MemoryRouter initialEntries={['/login']}><App /></MemoryRouter>)
    expect(await screen.findByRole('heading', { name: 'Bienvenido de nuevo' })).toBeInTheDocument()
    expect(screen.getByText(/no incluye credenciales predeterminadas/i)).toBeInTheDocument()
  })

  it('logs in using a cookie session and displays only real operational data', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = requestPath(input)
      if (path.endsWith('/auth/login')) return Promise.resolve(new Response(null, { status: 204 }))
      if (path.endsWith('/auth/session') && init?.method !== 'POST') return Promise.resolve(new Response(JSON.stringify(session), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      if (path.includes('/tickets/summary')) return Promise.resolve(new Response(JSON.stringify(emptySummary), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      if (path.includes('/tickets')) return Promise.resolve(new Response(JSON.stringify({ data: [], meta: { has_more: false, next_cursor: null } }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      return Promise.resolve(new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }))
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>)
    expect(await screen.findByRole('link', { name: 'Centro de operaciones' })).toBeInTheDocument()
    expect(screen.getByText('Modo local')).toBeInTheDocument()
    expect(screen.getByText('Rules · Sin LLM')).toBeInTheDocument()
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/v1/tickets/summary', expect.objectContaining({ credentials: 'include' })))
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/tickets?page_size=5', expect.objectContaining({ credentials: 'include' }))
  })

  it('submits credentials without storing or rendering the password', async () => {
    let authenticated = false
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = requestPath(input)
      if (path.endsWith('/auth/login')) { authenticated = true; return Promise.resolve(new Response(null, { status: 204 })) }
      if (path.endsWith('/auth/session') && authenticated) return Promise.resolve(new Response(JSON.stringify(session), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      return Promise.resolve(new Response(JSON.stringify({ detail: 'Authentication required' }), { status: 401, headers: { 'Content-Type': 'application/problem+json' } }))
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/login']}><App /></MemoryRouter>)
    fireEvent.change(await screen.findByLabelText('Identificador'), { target: { value: 'demo.requester' } })
    fireEvent.change(screen.getByLabelText('Contraseña'), { target: { value: 'local-secret' } })
    fireEvent.click(screen.getByRole('button', { name: /iniciar sesión/i }))
    expect(await screen.findByRole('link', { name: 'Centro de operaciones' })).toBeInTheDocument()
    expect(screen.queryByText('local-secret')).not.toBeInTheDocument()
  })

  it('traps modal focus, closes with Escape, and restores the trigger', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = requestPath(input)
      if (path.endsWith('/auth/session')) return Promise.resolve(new Response(JSON.stringify(session), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      if (path.includes('/tickets')) return Promise.resolve(new Response(JSON.stringify({ data: [], meta: { has_more: false, next_cursor: null } }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      return Promise.resolve(new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }))
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/tickets']}><App /></MemoryRouter>)
    const trigger = await screen.findByRole('button', { name: 'Nuevo ticket' })
    trigger.focus()
    fireEvent.click(trigger)
    const dialog = await screen.findByRole('dialog', { name: 'Crear ticket' })
    expect(screen.getByLabelText('Título')).toHaveFocus()

    const last = screen.getByRole('button', { name: 'Crear ticket' })
    last.focus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(screen.getByRole('button', { name: 'Cerrar' })).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Escape' })

    expect(dialog).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('uses the opaque cursor to navigate ticket pages', async () => {
    const ticket = (id: string, key: string) => ({ id, key, title: `Ticket ${key}`, description: 'Descripción sintética suficientemente larga.', category: 'network.vpn', impact: 'single_user', urgency: 'medium', priority: 'p3', status: 'new', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', assignee_id: null, resolution_summary: null, version: 1 })
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = requestPath(input)
      if (path.endsWith('/auth/session')) return Promise.resolve(new Response(JSON.stringify(session), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      if (path.includes('cursor=opaque-next')) return Promise.resolve(new Response(JSON.stringify({ data: [ticket('2', 'OPS-000002')], meta: { has_more: false, next_cursor: null } }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      if (path.includes('/tickets')) return Promise.resolve(new Response(JSON.stringify({ data: [ticket('1', 'OPS-000001')], meta: { has_more: true, next_cursor: 'opaque-next' } }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      return Promise.resolve(new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }))
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/tickets']}><App /></MemoryRouter>)
    expect(await screen.findByText('OPS-000001')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
    expect(await screen.findByText('OPS-000002')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/tickets?page_size=25&cursor=opaque-next', expect.objectContaining({ credentials: 'include' }))
    fireEvent.click(screen.getByRole('button', { name: 'Anterior' }))
    expect(await screen.findByText('OPS-000001')).toBeInTheDocument()
  })

  it('reuses the same idempotency key when ticket creation is retried', async () => {
    const idempotencyKeys: string[] = []
    let attempts = 0
    const createdTicket = { id: 'ticket-1', key: 'OPS-000001', title: 'Acceso VPN bloqueado', description: 'Descripción sintética suficientemente larga.', category: 'network.vpn', impact: 'single_user', urgency: 'medium', priority: 'p3', status: 'new', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', assignee_id: null, resolution_summary: null, version: 1 }
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = requestPath(input)
      if (path.endsWith('/auth/session')) return Promise.resolve(new Response(JSON.stringify(session), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      if (path === '/api/v1/tickets' && init?.method === 'POST') {
        idempotencyKeys.push(new Headers(init.headers).get('Idempotency-Key') ?? '')
        attempts += 1
        if (attempts === 1) return Promise.reject(new TypeError('network unavailable'))
        return Promise.resolve(new Response(JSON.stringify({ data: createdTicket }), { status: 201, headers: { 'Content-Type': 'application/json' } }))
      }
      if (path.includes('/tickets')) return Promise.resolve(new Response(JSON.stringify({ data: [], meta: { has_more: false, next_cursor: null } }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      return Promise.resolve(new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }))
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/tickets']}><App /></MemoryRouter>)
    fireEvent.click(await screen.findByRole('button', { name: 'Nuevo ticket' }))
    fireEvent.change(screen.getByLabelText('Título'), { target: { value: createdTicket.title } })
    fireEvent.change(screen.getByLabelText('Descripción'), { target: { value: createdTicket.description } })
    fireEvent.click(screen.getByRole('button', { name: 'Crear ticket' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Crear ticket' }))
    await waitFor(() => expect(attempts).toBe(2))
    expect(idempotencyKeys[0]).toBeTruthy()
    expect(idempotencyKeys[1]).toBe(idempotencyKeys[0])
  })

  it('renders only server-authorized transitions and discloses truncated history', async () => {
    const ticket = { id: 'ticket-1', key: 'OPS-000001', title: 'Acceso VPN bloqueado', description: 'Descripción sintética suficientemente larga.', category: 'network.vpn', impact: 'single_user', urgency: 'medium', priority: 'p3', status: 'new', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', assignee_id: null, resolution_summary: null, version: 1 }
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = requestPath(input)
      if (path.endsWith('/auth/session')) return Promise.resolve(new Response(JSON.stringify(session), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      if (path.endsWith('/transition-options')) return Promise.resolve(new Response(JSON.stringify({ data: [{ target: 'cancelled', required_fields: [] }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      if (path.includes('/timeline')) return Promise.resolve(new Response(JSON.stringify({ data: [{ type: 'ticket_created', actor_role: 'requester', occurred_at: '2026-01-01T00:00:00Z', revision: 1 }], meta: { has_more: true, next_cursor: 'opaque' } }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      if (path.endsWith('/tickets/ticket-1')) return Promise.resolve(new Response(JSON.stringify({ data: ticket }), { status: 200, headers: { 'Content-Type': 'application/json', ETag: '"1"' } }))
      return Promise.resolve(new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }))
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/tickets/ticket-1']}><App /></MemoryRouter>)
    expect(await screen.findByRole('button', { name: 'Cancelado' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Clasificado' })).not.toBeInTheDocument()
    expect(screen.getByText('Mostrando los primeros 1 eventos')).toBeInTheDocument()
  })
})
