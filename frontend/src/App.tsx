import {
  Activity,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronDown,
  ClipboardList,
  FilePlus2,
  Gauge,
  LoaderCircle,
  MapPin,
  MessageSquareText,
  RotateCw,
  Send,
  ShieldAlert,
  Siren,
  Waves,
} from 'lucide-react'
import {
  Component,
  type ErrorInfo,
  type FormEvent,
  useEffect,
  useState,
} from 'react'
import {
  ApiError,
  categories,
  createComplaint,
  getStats,
  listComplaints,
  priorities,
  statuses,
  updateComplaintStatus,
  type Complaint,
  type ComplaintCategory,
  type ComplaintDraft,
  type ComplaintPriority,
  type ComplaintStatus,
  type Stats,
} from './api'
import './civicpulse.css'

type View = 'queue' | 'submit' | 'stats'

const viewItems: { id: View; label: string; icon: typeof ClipboardList }[] = [
  { id: 'queue', label: 'Queue', icon: ClipboardList },
  { id: 'submit', label: 'New report', icon: FilePlus2 },
  { id: 'stats', label: 'Overview', icon: Activity },
]

export default function App() {
  const [view, setView] = useState<View>('queue')

  return (
    <ErrorBoundary>
      <div className="app-shell">
        <header className="topbar">
          <a className="brand" href="#queue" onClick={() => setView('queue')}>
            <span className="brand-mark" aria-hidden="true"><Waves size={21} strokeWidth={2.4} /></span>
            <span className="brand-copy"><strong>CivicPulse</strong><small>City operations</small></span>
          </a>
          <nav className="primary-nav" aria-label="Main navigation">
            {viewItems.map(({ id, label, icon: Icon }) => (
              <button
                aria-current={view === id ? 'page' : undefined}
                className={`nav-link${view === id ? ' active' : ''}`}
                key={id}
                onClick={() => setView(id)}
                type="button"
              >
                <Icon aria-hidden="true" size={17} />
                <span>{label}</span>
              </button>
            ))}
          </nav>
          <div className="topbar-meta"><span className="pulse-dot" />Service desk</div>
        </header>

        <main className="workspace">
          {view === 'queue' && <DashboardView />}
          {view === 'submit' && <SubmitView />}
          {view === 'stats' && <StatsView />}
        </main>

        <footer className="site-footer">
          <span>CivicPulse <span aria-hidden="true">/</span> Operations</span>
          <span>Public service response desk</span>
        </footer>
      </div>
    </ErrorBoundary>
  )
}

type ErrorBoundaryState = { hasError: boolean }

export class ErrorBoundary extends Component<{ children: React.ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('CivicPulse view failed', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="boundary-fallback" role="alert">
          <ShieldAlert aria-hidden="true" size={24} />
          <h1>This view could not be loaded.</h1>
          <p>Reload the page to continue.</p>
        </main>
      )
    }
    return this.props.children
  }
}

const emptyDraft: ComplaintDraft = { text: '', location: '', reporter_contact: '' }

function validateDraft(draft: ComplaintDraft): Partial<Record<keyof ComplaintDraft, string>> {
  const errors: Partial<Record<keyof ComplaintDraft, string>> = {}
  const textLength = draft.text.trim().length
  const locationLength = draft.location.trim().length
  if (textLength < 10 || textLength > 2000) {
    errors.text = 'Description must be between 10 and 2000 characters.'
  }
  if (locationLength < 3 || locationLength > 200) {
    errors.location = 'Location must be between 3 and 200 characters.'
  }
  if (draft.reporter_contact.length > 255) {
    errors.reporter_contact = 'Contact must be 255 characters or fewer.'
  }
  return errors
}

export function SubmitView() {
  const [draft, setDraft] = useState<ComplaintDraft>(emptyDraft)
  const [errors, setErrors] = useState<Partial<Record<keyof ComplaintDraft, string>>>({})
  const [created, setCreated] = useState<Complaint | null>(null)
  const [requestError, setRequestError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const handleChange = (field: keyof ComplaintDraft, value: string) => {
    setDraft((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: undefined }))
    setRequestError(null)
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const validation = validateDraft(draft)
    setErrors(validation)
    setCreated(null)
    setRequestError(null)
    if (Object.keys(validation).length > 0) return

    setSubmitting(true)
    try {
      const result = await createComplaint({
        text: draft.text.trim(),
        location: draft.location.trim(),
        reporter_contact: draft.reporter_contact.trim() || null,
      })
      setCreated(result)
    } catch (error) {
      setRequestError(errorMessage(error))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section aria-labelledby="submit-title" className="view-section">
      <ViewHeading id="submit-title" eyebrow="INTAKE / NEW CASE" title="Report a civic issue" icon={FilePlus2} />
      <div className="submit-layout">
        <form aria-label="New complaint" className="report-form" noValidate onSubmit={handleSubmit}>
          <div className="form-section-heading"><span>01</span><h2>Issue details</h2></div>
          <label htmlFor="complaint-text">Description <span className="required-mark">Required</span></label>
          <textarea
            aria-describedby={errors.text ? 'text-error' : 'text-hint'}
            aria-invalid={Boolean(errors.text)}
            id="complaint-text"
            maxLength={2000}
            onChange={(event) => handleChange('text', event.target.value)}
            placeholder="Water service, road damage, street lighting..."
            rows={6}
            value={draft.text}
          />
          <div className="field-footnote">
            {errors.text ? <span className="field-error" id="text-error">{errors.text}</span> : <span id="text-hint">Describe the location and impact.</span>}
            <span className="character-count">{draft.text.length} / 2000</span>
          </div>

          <div className="form-grid">
            <div className="field-group">
              <label htmlFor="complaint-location">Location <span className="required-mark">Required</span></label>
              <div className="input-with-icon">
                <MapPin aria-hidden="true" size={17} />
                <input
                  aria-describedby={errors.location ? 'location-error' : undefined}
                  aria-invalid={Boolean(errors.location)}
                  autoComplete="street-address"
                  id="complaint-location"
                  maxLength={200}
                  onChange={(event) => handleChange('location', event.target.value)}
                  placeholder="Street, district, or landmark"
                  value={draft.location}
                />
              </div>
              {errors.location && <span className="field-error" id="location-error">{errors.location}</span>}
            </div>
            <div className="field-group">
              <label htmlFor="reporter-contact">Contact <span className="optional-mark">Optional</span></label>
              <input
                aria-describedby={errors.reporter_contact ? 'contact-error' : undefined}
                aria-invalid={Boolean(errors.reporter_contact)}
                autoComplete="email"
                id="reporter-contact"
                maxLength={255}
                onChange={(event) => handleChange('reporter_contact', event.target.value)}
                placeholder="Email or phone"
                value={draft.reporter_contact}
              />
              {errors.reporter_contact && <span className="field-error" id="contact-error">{errors.reporter_contact}</span>}
            </div>
          </div>

          {requestError && <p className="inline-alert" role="alert">{requestError}</p>}
          <div className="form-actions">
            <span className="form-note"><ShieldAlert aria-hidden="true" size={15} /> Personal contact is not required</span>
            <button className="button button-primary" disabled={submitting} type="submit">
              {submitting ? <LoaderCircle aria-hidden="true" className="spin" size={17} /> : <Send aria-hidden="true" size={16} />}
              {submitting ? 'Submitting' : 'Submit report'}
            </button>
          </div>
        </form>

        <aside aria-label="Submission status" className="submit-aside">
          {created ? (
            <div className="result-panel" role="status">
              <div className="result-topline"><span className="success-icon"><Check size={18} /></span><span>REPORT RECEIVED</span></div>
              <p className="result-id">Case {created.id.slice(0, 8).toUpperCase()}</p>
              <h2>Triage complete</h2>
              <p className="result-summary">{created.ai_summary ?? created.text}</p>
              <dl className="result-details">
                <div><dt>Category</dt><dd>{created.category}</dd></div>
                <div><dt>Priority</dt><dd><PriorityPill priority={created.priority} /></dd></div>
                <div><dt>Provider</dt><dd>{created.triaged_by}</dd></div>
              </dl>
              <p className="latency-note">{created.triage_latency_ms} ms triage latency</p>
            </div>
          ) : (
            <div className="aside-quiet">
              <span className="aside-icon"><Siren aria-hidden="true" size={22} /></span>
              <span className="eyebrow">INCOMING REPORT</span>
              <h2>Ready for intake</h2>
              <div className="aside-rule" />
              <div className="aside-meta"><span>Classification</span><strong>Automatic triage</strong></div>
              <div className="aside-meta"><span>Initial status</span><strong>Open</strong></div>
            </div>
          )}
        </aside>
      </div>
    </section>
  )
}

const pageSize = 10

export function DashboardView() {
  const [category, setCategory] = useState<ComplaintCategory | ''>('')
  const [priority, setPriority] = useState<ComplaintPriority | ''>('')
  const [status, setStatus] = useState<ComplaintStatus | ''>('')
  const [page, setPage] = useState(1)
  const [items, setItems] = useState<Complaint[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [selectedStatuses, setSelectedStatuses] = useState<Record<string, ComplaintStatus>>({})
  const [savingId, setSavingId] = useState<string | null>(null)
  const [refreshVersion, setRefreshVersion] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    void listComplaints({ category, priority, status, page, page_size: pageSize }, controller.signal)
      .then((response) => {
        setItems(response.items)
        setTotal(response.total)
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setLoadError(errorMessage(error))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [category, priority, status, page, refreshVersion])

  const handleStatusUpdate = async (complaint: Complaint) => {
    const nextStatus = selectedStatuses[complaint.id] ?? complaint.status
    setSavingId(complaint.id)
    setActionError(null)
    try {
      const updated = await updateComplaintStatus(complaint.id, nextStatus)
      setItems((current) => current.map((item) => item.id === updated.id ? updated : item))
      setSelectedStatuses((current) => ({ ...current, [updated.id]: updated.status }))
      setLoading(true)
      setRefreshVersion((current) => current + 1)
    } catch (error) {
      setActionError(errorMessage(error))
    } finally {
      setSavingId(null)
    }
  }

  const changeCategory = (value: ComplaintCategory | '') => {
    setCategory(value)
    setPage(1)
    setLoading(true)
    setLoadError(null)
  }
  const changePriority = (value: ComplaintPriority | '') => {
    setPriority(value)
    setPage(1)
    setLoading(true)
    setLoadError(null)
  }
  const changeStatus = (value: ComplaintStatus | '') => {
    setStatus(value)
    setPage(1)
    setLoading(true)
    setLoadError(null)
  }
  const changePage = (nextPage: number) => {
    setPage(nextPage)
    setLoading(true)
    setLoadError(null)
  }
  const pageCount = Math.max(1, Math.ceil(total / pageSize))

  return (
    <section aria-labelledby="queue-title" className="view-section">
      <ViewHeading id="queue-title" eyebrow="OPERATIONS / COMPLAINT QUEUE" title="Response queue" icon={ClipboardList} />
      <div className="queue-toolbar">
        <div className="queue-total"><strong>{total}</strong><span>tracked reports</span></div>
        <div className="filters" aria-label="Complaint filters">
          <label><span>Category</span><select aria-label="Filter by category" onChange={(event) => changeCategory(event.target.value as ComplaintCategory | '')} value={category}>
            <option value="">All categories</option>{categories.map((value) => <option key={value} value={value}>{value}</option>)}
          </select><ChevronDown aria-hidden="true" size={13} /></label>
          <label><span>Priority</span><select aria-label="Filter by priority" onChange={(event) => changePriority(event.target.value as ComplaintPriority | '')} value={priority}>
            <option value="">All priorities</option>{priorities.map((value) => <option key={value} value={value}>{value}</option>)}
          </select><ChevronDown aria-hidden="true" size={13} /></label>
          <label><span>Status</span><select aria-label="Filter by status" onChange={(event) => changeStatus(event.target.value as ComplaintStatus | '')} value={status}>
            <option value="">All statuses</option>{statuses.map((value) => <option key={value} value={value}>{statusLabel(value)}</option>)}
          </select><ChevronDown aria-hidden="true" size={13} /></label>
        </div>
      </div>

      {actionError && <p className="inline-alert conflict-alert" role="alert">{actionError}</p>}
      {loadError && <p className="inline-alert" role="alert">{loadError}</p>}
      <div aria-busy={loading} className="queue-table-wrap">
        <div className="queue-table-head" aria-hidden="true">
          <span>Report</span><span>Location</span><span>Priority</span><span>Status</span><span>Update</span>
        </div>
        {loading ? (
          <div className="loading-row"><LoaderCircle aria-hidden="true" className="spin" size={20} /> Loading reports</div>
        ) : items.length === 0 ? (
          <div className="empty-state"><ClipboardList aria-hidden="true" size={25} /><strong>No reports found</strong><span>Change filters or submit a new report.</span></div>
        ) : (
          <div className="queue-rows">
            {items.map((complaint) => (
              <article className="queue-row" key={complaint.id}>
                <div className="report-cell"><span className="category-label">{complaint.category}</span><strong>{complaint.text}</strong><time dateTime={complaint.created_at}>{formatDate(complaint.created_at)}</time></div>
                <div className="location-cell"><MapPin aria-hidden="true" size={14} />{complaint.location}</div>
                <div><PriorityPill priority={complaint.priority} /></div>
                <div><StatusPill status={complaint.status} /></div>
                <div className="status-action">
                  <label className="visually-hidden" htmlFor={`status-${complaint.id}`}>New status for {complaint.id}</label>
                  <select
                    aria-label={`New status for ${complaint.id}`}
                    id={`status-${complaint.id}`}
                    onChange={(event) => setSelectedStatuses((current) => ({ ...current, [complaint.id]: event.target.value as ComplaintStatus }))}
                    value={selectedStatuses[complaint.id] ?? complaint.status}
                  >
                    {statuses.map((value) => <option key={value} value={value}>{statusLabel(value)}</option>)}
                  </select>
                  <button aria-label={`Save status for ${complaint.id}`} className="icon-button" disabled={savingId === complaint.id} onClick={() => void handleStatusUpdate(complaint)} title="Save status" type="button">
                    {savingId === complaint.id ? <LoaderCircle aria-hidden="true" className="spin" size={16} /> : <Check aria-hidden="true" size={16} />}
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
      <div className="pagination">
        <span>Page {page} of {pageCount}</span>
        <div>
          <button aria-label="Previous page" className="icon-button" disabled={page <= 1 || loading} onClick={() => changePage(page - 1)} type="button"><ArrowLeft aria-hidden="true" size={16} /></button>
          <button aria-label="Next page" className="icon-button" disabled={page >= pageCount || loading} onClick={() => changePage(page + 1)} type="button"><ArrowRight aria-hidden="true" size={16} /></button>
        </div>
      </div>
    </section>
  )
}

export function StatsView() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [cache, setCache] = useState<'HIT' | 'MISS' | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    let current = true
    void getStats()
      .then((result) => {
        if (!current) return
        setStats(result.stats)
        setCache(result.cache)
      })
      .catch((reason: unknown) => {
        if (current) setError(errorMessage(reason))
      })
      .finally(() => {
        if (current) setLoading(false)
      })
    return () => { current = false }
  }, [refreshKey])

  const refresh = () => {
    setLoading(true)
    setError(null)
    setRefreshKey((current) => current + 1)
  }

  return (
    <section aria-labelledby="stats-title" className="view-section">
      <ViewHeading id="stats-title" eyebrow="INTELLIGENCE / SERVICE SNAPSHOT" title="City pulse" icon={Gauge} />
      <div className="stats-toolbar">
        <p>Complaint volume and triage performance</p>
        <div className="stats-toolbar-actions">
          {cache && <span className={`cache-badge cache-${cache.toLowerCase()}`}><span />Cache {cache}</span>}
          <button aria-label="Refresh statistics" className="icon-button" disabled={loading} onClick={refresh} title="Refresh statistics" type="button">
            {loading ? <LoaderCircle aria-hidden="true" className="spin" size={16} /> : <RotateCw aria-hidden="true" size={16} />}
          </button>
        </div>
      </div>
      {error && <p className="inline-alert" role="alert">{error}</p>}
      {loading && !stats ? (
        <div className="loading-row"><LoaderCircle aria-hidden="true" className="spin" size={20} /> Loading statistics</div>
      ) : stats ? (
        <div aria-busy={loading} className="stats-content">
          <div className="metric-grid">
            <Metric label="All reports" value={stats.total} icon={MessageSquareText} tone="green" />
            <Metric label="Open" value={stats.by_status.open} icon={Siren} tone="rust" />
            <Metric label="In progress" value={stats.by_status.in_progress} icon={ArrowUpRight} tone="blue" />
            <Metric label="Resolved" value={stats.by_status.resolved} icon={Check} tone="olive" />
          </div>
          <div className="stats-breakdown">
            <section aria-labelledby="category-counts" className="breakdown-section">
              <div className="breakdown-heading"><h2 id="category-counts">Reports by category</h2><span>{Object.keys(stats.by_category).length} services</span></div>
              <CountBars values={stats.by_category} />
            </section>
            <section aria-labelledby="priority-counts" className="breakdown-section priority-breakdown">
              <div className="breakdown-heading"><h2 id="priority-counts">Priority mix</h2><span>{stats.total} total</span></div>
              <CountBars values={stats.by_priority} />
              <div className="latency-stat"><span>Average triage latency</span><strong>{stats.avg_triage_latency_ms}<small> ms</small></strong></div>
            </section>
          </div>
        </div>
      ) : null}
      <div className="stats-footnote"><Activity aria-hidden="true" size={15} /> Aggregates reflect the full complaint register.</div>
    </section>
  )
}

function CountBars({ values }: { values: Record<string, number> }) {
  const maximum = Math.max(1, ...Object.values(values))
  return (
    <div className="count-bars">
      {Object.entries(values).map(([label, value]) => (
        <div className="count-bar-row" key={label}>
          <span>{label.replaceAll('_', ' ')}</span>
          <div aria-hidden="true" className="bar-track"><span style={{ width: `${Math.max(value > 0 ? 3 : 0, (value / maximum) * 100)}%` }} /></div>
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  )
}

function Metric({ label, value, icon: Icon, tone }: { label: string; value: number; icon: typeof Gauge; tone: string }) {
  return (
    <div className={`metric-item tone-${tone}`}>
      <span className="metric-icon"><Icon aria-hidden="true" size={19} /></span>
      <span className="metric-label">{label}</span>
      <strong>{value.toLocaleString()}</strong>
    </div>
  )
}

function ViewHeading({ id, eyebrow, title, icon: Icon }: { id: string; eyebrow: string; title: string; icon: typeof Gauge }) {
  return (
    <div className="view-heading">
      <div><span className="eyebrow">{eyebrow}</span><h1 id={id}>{title}</h1></div>
      <span className="heading-icon"><Icon aria-hidden="true" size={22} /></span>
    </div>
  )
}

function PriorityPill({ priority }: { priority: ComplaintPriority }) {
  return <span className={`priority-pill priority-${priority}`}><span />{priority}</span>
}

function StatusPill({ status }: { status: ComplaintStatus }) {
  return <span className={`status-pill status-${status}`}>{statusLabel(status)}</span>
}

function statusLabel(status: ComplaintStatus): string {
  return status.replaceAll('_', ' ')
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value))
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.detail
  if (error instanceof Error) return error.message
  return 'The request could not be completed.'
}
