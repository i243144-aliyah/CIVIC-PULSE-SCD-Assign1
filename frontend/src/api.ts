export const categories = [
  'water',
  'electricity',
  'sanitation',
  'roads',
  'streetlights',
  'other',
] as const

export const priorities = ['high', 'normal', 'low'] as const
export const statuses = ['open', 'in_progress', 'resolved', 'rejected'] as const

export type ComplaintCategory = (typeof categories)[number]
export type ComplaintPriority = (typeof priorities)[number]
export type ComplaintStatus = (typeof statuses)[number]
export type TriagedBy = 'llm:groq' | 'llm:ollama' | 'rules' | 'rules:fallback'

export interface ComplaintDraft {
  text: string
  location: string
  reporter_contact: string
}

export interface CreateComplaintRequest {
  text: string
  location: string
  reporter_contact?: string | null
  category?: ComplaintCategory | null
}

export interface Complaint {
  id: string
  text: string
  location: string
  reporter_contact: string | null
  category: ComplaintCategory
  priority: ComplaintPriority
  status: ComplaintStatus
  ai_summary: string | null
  triaged_by: TriagedBy
  triage_latency_ms: number
  created_at: string
  updated_at: string
}

export interface ComplaintListResponse {
  items: Complaint[]
  total: number
  page: number
  page_size: number
}

export interface ComplaintFilters {
  category?: ComplaintCategory | ''
  priority?: ComplaintPriority | ''
  status?: ComplaintStatus | ''
  page?: number
  page_size?: number
}

export interface Stats {
  total: number
  by_status: Record<ComplaintStatus, number>
  by_priority: Record<ComplaintPriority, number>
  by_category: Record<ComplaintCategory, number>
  avg_triage_latency_ms: number
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function detailFromPayload(payload: unknown, fallback: string): string {
  if (!isRecord(payload) || !('detail' in payload)) return fallback
  const detail = payload.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      if (!isRecord(item)) return String(item)
      const field = typeof item.field === 'string' ? item.field : ''
      const message = typeof item.message === 'string' ? item.message : 'Invalid value'
      return field ? `${field}: ${message}` : message
    }).join('\n')
  }
  return fallback
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<{ data: T; response: Response }> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const response = await fetch(`/api${path}`, { ...init, headers })
  let payload: unknown = null
  try {
    payload = await response.json() as unknown
  } catch {
    // Error responses without JSON use the status-based fallback message.
  }
  if (!response.ok) {
    throw new ApiError(response.status, detailFromPayload(payload, `Request failed (${response.status}).`))
  }
  return { data: payload as T, response }
}

export async function createComplaint(body: CreateComplaintRequest): Promise<Complaint> {
  const { data } = await requestJson<Complaint>('/complaints', {
    method: 'POST',
    body: JSON.stringify(body),
  })
  return data
}

export async function listComplaints(
  filters: ComplaintFilters,
  signal?: AbortSignal,
): Promise<ComplaintListResponse> {
  const params = new URLSearchParams()
  for (const key of ['category', 'priority', 'status'] as const) {
    const value = filters[key]
    if (value) params.set(key, value)
  }
  params.set('page', String(filters.page ?? 1))
  params.set('page_size', String(filters.page_size ?? 20))
  const { data } = await requestJson<ComplaintListResponse>(`/complaints?${params}`, { signal })
  return data
}

export async function updateComplaintStatus(
  complaintId: string,
  status: ComplaintStatus,
): Promise<Complaint> {
  const { data } = await requestJson<Complaint>(`/complaints/${encodeURIComponent(complaintId)}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
  return data
}

export async function getStats(): Promise<{ stats: Stats; cache: 'HIT' | 'MISS' | null }> {
  const { data, response } = await requestJson<Stats>('/stats')
  const header = response.headers.get('X-Cache')?.toUpperCase()
  return { stats: data, cache: header === 'HIT' || header === 'MISS' ? header : null }
}