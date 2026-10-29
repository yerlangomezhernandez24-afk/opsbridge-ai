export type Role = 'requester' | 'technician' | 'approver'
export type TicketStatus = 'new' | 'triaged' | 'in_progress' | 'waiting_approval' | 'waiting_requester' | 'resolved' | 'closed' | 'cancelled'
export type TicketPriority = 'p1' | 'p2' | 'p3' | 'p4'
export type TicketCategory = 'network.vpn' | 'software.application' | 'hardware.endpoint' | 'access.application'

export interface Session {
  user_id: string
  login_id: string
  display_name: string
  role: Role
  permissions: string[]
  csrf_token: string
  expires_at: string
}

export interface Ticket {
  id: string
  key: string
  title: string
  description: string
  category: TicketCategory
  impact: 'single_user' | 'multiple_users' | 'organization'
  urgency: 'low' | 'medium' | 'high'
  priority: TicketPriority
  status: TicketStatus
  created_at: string
  updated_at: string
  assignee_id: string | null
  resolution_summary: string | null
  version: number
}

export interface NamedTicketCount { name: string; value: number }
export interface DailyTicketCount { day: string; value: number }
export interface TicketSummary {
  total: number
  by_status: NamedTicketCount[]
  by_priority: NamedTicketCount[]
  by_category: NamedTicketCount[]
  created_by_day: DailyTicketCount[]
}

export interface TicketEvent { type: string; actor_role: string; occurred_at: string; revision: number }
export interface TransitionOption { target: TicketStatus; required_fields: TransitionField[] }
export type TransitionField = 'reason' | 'resolution_summary' | 'requester_response_received' | 'requester_confirmed'
export interface TransitionPayload {
  target: TicketStatus
  reason?: string
  resolution_summary?: string
  requester_response_received?: boolean
  requester_confirmed?: boolean
}
export interface TimelineResult { events: TicketEvent[]; hasMore: boolean }
export interface Problem { type?: string; title?: string; status?: number; detail?: string; code?: string; correlation_id?: string }

export interface Citation { document_code: string; document_title: string; document_version: string; chunk_id: string; heading: string; content: string; score: number; href: string }
export interface KnowledgeResult { mode: string; query: string; abstained: boolean; citations: Citation[] }
export interface ActionProposal { id: string; ticket_id: string; ticket_version: number; action_type: string; source_mode: string; arguments: Record<string, unknown>; arguments_hash: string; proposer_id: string; status: string; created_at: string; expires_at: string; decision_actor_id: string | null; decided_at: string | null; decision_reason: string | null }
export interface ActionExecution { id: string; proposal_id: string; status: string; result: Record<string, unknown>; executed_at: string }
export interface AiStatus { rules_available: boolean; retrieval_mode: string; llm_local_available: boolean; llm_local_verified: boolean; provider: string; status: string }
