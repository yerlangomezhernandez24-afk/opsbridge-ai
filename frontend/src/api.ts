import type { ActionExecution, ActionProposal, AiStatus, KnowledgeResult, Problem, Session, Ticket, TicketCategory, TicketEvent, TicketSummary, TimelineResult, TransitionOption, TransitionPayload } from './types'

export class ApiError extends Error {
  constructor(public status: number, public problem: Problem) {
    super(problem.detail ?? problem.title ?? `Error HTTP ${status}`)
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<{ data: T; response: Response }> {
  const response = await fetch(path, { ...init, credentials: 'include', headers: { Accept: 'application/json', ...init.headers } })
  if (!response.ok) {
    let problem: Problem = { status: response.status, detail: 'No fue posible completar la solicitud.' }
    try { problem = await response.json() as Problem } catch { /* respuesta no JSON */ }
    throw new ApiError(response.status, problem)
  }
  const data = response.status === 204 ? undefined as T : await response.json() as T
  return { data, response }
}

const mutationHeaders = (csrf: string): HeadersInit => ({ 'Content-Type': 'application/json', 'X-CSRF-Token': csrf })

export const api = {
  login: (login_id: string, password: string) => request<void>('/api/v1/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ login_id, password }) }),
  session: async () => (await request<Session>('/api/v1/auth/session')).data,
  logout: (csrf: string) => request<void>('/api/v1/auth/logout', { method: 'POST', headers: mutationHeaders(csrf) }),
  listTickets: async (params = '') => (await request<{ data: Ticket[]; meta: { next_cursor: string | null; has_more: boolean } }>(`/api/v1/tickets${params}`)).data,
  ticketSummary: async (params = '') => (await request<{ data: TicketSummary }>(`/api/v1/tickets/summary${params}`)).data.data,
  getTicket: async (id: string) => {
    const result = await request<{ data: Ticket }>(`/api/v1/tickets/${id}`)
    return { ticket: result.data.data, etag: result.response.headers.get('ETag') ?? `"${result.data.data.version}"` }
  },
  createTicket: async (csrf: string, payload: { title: string; description: string; category: TicketCategory; impact: string; urgency: string }, idempotencyKey: string) =>
    (await request<{ data: Ticket }>('/api/v1/tickets', { method: 'POST', headers: { ...mutationHeaders(csrf), 'Idempotency-Key': idempotencyKey }, body: JSON.stringify(payload) })).data.data,
  patchTicket: async (csrf: string, id: string, etag: string, payload: { category?: TicketCategory; impact?: string; urgency?: string }) =>
    (await request<{ data: Ticket }>(`/api/v1/tickets/${id}`, { method: 'PATCH', headers: { ...mutationHeaders(csrf), 'If-Match': etag }, body: JSON.stringify(payload) })).data.data,
  transitionOptions: async (id: string) => (await request<{ data: TransitionOption[] }>(`/api/v1/tickets/${id}/transition-options`)).data.data,
  transitionTicket: async (csrf: string, id: string, etag: string, payload: TransitionPayload) =>
    (await request<{ data: Ticket }>(`/api/v1/tickets/${id}/transitions`, { method: 'POST', headers: { ...mutationHeaders(csrf), 'If-Match': etag }, body: JSON.stringify(payload) })).data.data,
  timeline: async (id: string): Promise<TimelineResult> => {
    const result = await request<{ data: TicketEvent[]; meta: { has_more: boolean } }>(`/api/v1/tickets/${id}/timeline?page_size=100`)
    return { events: result.data.data, hasMore: result.data.meta.has_more }
  },
  searchKnowledge: async (query: string) => (await request<KnowledgeResult>(`/api/v1/knowledge/search?q=${encodeURIComponent(query)}&limit=5`)).data,
  listProposals: async () => (await request<{ data: ActionProposal[] }>('/api/v1/approval-requests')).data.data,
  proposeVpnReset: async (csrf: string, ticketId: string, etag: string, identity_code: string) =>
    (await request<{ data: ActionProposal }>(`/api/v1/tickets/${ticketId}/action-proposals`, { method: 'POST', headers: { ...mutationHeaders(csrf), 'If-Match': etag }, body: JSON.stringify({ identity_code, source_mode: 'rules' }) })).data.data,
  decideProposal: async (csrf: string, proposalId: string, decision: 'approve' | 'reject', reason: string) =>
    (await request<{ data: ActionProposal }>(`/api/v1/approval-requests/${proposalId}/decisions`, { method: 'POST', headers: mutationHeaders(csrf), body: JSON.stringify({ decision, reason }) })).data.data,
  executeProposal: async (csrf: string, proposalId: string) =>
    (await request<{ data: ActionExecution }>(`/api/v1/approval-requests/${proposalId}/executions`, { method: 'POST', headers: mutationHeaders(csrf) })).data.data,
  aiStatus: async () => (await request<{ data: AiStatus }>('/api/v1/ai/status')).data.data,
  health: async () => (await request<{ status: string }>('/health/ready')).data,
}
