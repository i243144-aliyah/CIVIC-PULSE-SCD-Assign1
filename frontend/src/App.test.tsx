import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DashboardView, StatsView, SubmitView } from './App'
import type { Complaint, ComplaintListResponse, Stats } from './api'

const fetchMock = vi.fn<typeof fetch>()

const complaint: Complaint = {
  id: 'case-001',
  text: 'Large pothole beside the public school gate',
  location: 'School Road, Ward 4',
  reporter_contact: null,
  category: 'roads',
  priority: 'high',
  status: 'resolved',
  ai_summary: 'Large pothole beside the school entrance',
  triaged_by: 'rules',
  triage_latency_ms: 14,
  created_at: '2026-09-20T08:30:00Z',
  updated_at: '2026-09-21T10:15:00Z',
}

const complaintList: ComplaintListResponse = {
  items: [complaint],
  total: 1,
  page: 1,
  page_size: 10,
}

const stats: Stats = {
  total: 8,
  by_status: { open: 3, in_progress: 2, resolved: 2, rejected: 1 },
  by_priority: { high: 2, normal: 4, low: 2 },
  by_category: { water: 2, electricity: 1, sanitation: 1, roads: 2, streetlights: 1, other: 1 },
  avg_triage_latency_ms: 18.25,
}

function jsonResponse(body: unknown, status = 200, headers: HeadersInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...Object.fromEntries(new Headers(headers).entries()) },
  })
}

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => cleanup())

describe('CivicPulse views', () => {
  it('validates complaint text and location before sending', async () => {
    render(<SubmitView />)
    fireEvent.change(screen.getByLabelText(/description/i), { target: { value: 'short' } })
    fireEvent.change(screen.getByLabelText(/location/i), { target: { value: 'AB' } })
    fireEvent.submit(screen.getByRole('form', { name: 'New complaint' }))

    expect(await screen.findByText('Description must be between 10 and 2000 characters.')).toBeInTheDocument()
    expect(screen.getByText('Location must be between 3 and 200 characters.')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows the returned triage result after a successful submission', async () => {
    const created = { ...complaint, status: 'open' as const }
    fetchMock.mockResolvedValueOnce(jsonResponse(created, 201))
    render(<SubmitView />)
    fireEvent.change(screen.getByLabelText(/description/i), { target: { value: complaint.text } })
    fireEvent.change(screen.getByLabelText(/location/i), { target: { value: complaint.location } })
    fireEvent.click(screen.getByRole('button', { name: /submit report/i }))

    expect(await screen.findByText('Triage complete')).toBeInTheDocument()
    expect(screen.getByText('roads')).toBeInTheDocument()
    expect(screen.getByText('rules')).toBeInTheDocument()
    expect(screen.getByText(complaint.ai_summary as string)).toBeInTheDocument()
  })

  it('shows an active disabled loading state while submitting', async () => {
    let resolveResponse: ((response: Response) => void) | undefined
    fetchMock.mockReturnValueOnce(new Promise((resolve) => { resolveResponse = resolve }))
    render(<SubmitView />)
    fireEvent.change(screen.getByLabelText(/description/i), { target: { value: complaint.text } })
    fireEvent.change(screen.getByLabelText(/location/i), { target: { value: complaint.location } })
    fireEvent.click(screen.getByRole('button', { name: /submit report/i }))

    const submittingButton = await screen.findByRole('button', { name: /submitting/i })
    expect(submittingButton).toBeDisabled()
    resolveResponse?.(jsonResponse({ ...complaint, status: 'open' }))
    expect(await screen.findByText('Triage complete')).toBeInTheDocument()
  })

  it('renders the backend 409 transition detail verbatim', async () => {
    const conflict = "Cannot transition from 'resolved' to 'open'. Allowed transitions: []."
    fetchMock
      .mockResolvedValueOnce(jsonResponse(complaintList))
      .mockResolvedValueOnce(jsonResponse({ detail: conflict }, 409))
    render(<DashboardView />)
    const statusSelect = await screen.findByRole('combobox', { name: `New status for ${complaint.id}` })
    fireEvent.change(statusSelect, { target: { value: 'open' } })
    fireEvent.click(screen.getByRole('button', { name: `Save status for ${complaint.id}` }))

    expect(await screen.findByRole('alert')).toHaveTextContent(conflict)
    expect(screen.getByRole('alert')).toHaveTextContent(/^Cannot transition from 'resolved' to 'open'\. Allowed transitions: \[\]\.$/)
  })

  it('shows a HIT badge and aggregate counts from stats', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(stats, 200, { 'X-Cache': 'HIT' }))
    render(<StatsView />)

    expect(await screen.findByText('Cache HIT')).toBeInTheDocument()
    expect(screen.getByText('18.25')).toBeInTheDocument()
    expect(screen.getByText('All reports').parentElement).toHaveTextContent('8')
  })

  it('shows a MISS badge from the stats response header', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(stats, 200, { 'X-Cache': 'MISS' }))
    render(<StatsView />)

    expect(await screen.findByText('Cache MISS')).toBeInTheDocument()
  })

  it('requests the queue using typed filter and pagination parameters', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(complaintList))
    render(<DashboardView />)
    await screen.findByText(complaint.text)
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/complaints?page=1&page_size=10',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    ))
  })
})