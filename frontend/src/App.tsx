import { type FormEvent, type ReactNode, lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Activity, BarChart3, BookOpen, Bot, CheckCircle2, ChevronRight, CircleUserRound, ClipboardCheck, LayoutDashboard, LifeBuoy, ListFilter, LogOut, Menu, Moon, Plus, RefreshCw, Search, Settings, ShieldCheck, Sun, TicketCheck, X } from 'lucide-react'
import { Link, Navigate, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import { ApiError, api } from './api'
import type { ActionProposal, Session, Ticket, TicketCategory, TicketEvent, TicketStatus } from './types'

const StatusBarChart = lazy(() => import('./OperationalCharts').then(module => ({ default: module.StatusBarChart })))
const PriorityPieChart = lazy(() => import('./OperationalCharts').then(module => ({ default: module.PriorityPieChart })))
const DailyVolumeChart = lazy(() => import('./OperationalCharts').then(module => ({ default: module.DailyVolumeChart })))

const statusLabels: Record<TicketStatus, string> = { new: 'Nuevo', triaged: 'Clasificado', in_progress: 'En progreso', waiting_requester: 'Esperando solicitante', waiting_approval: 'Pendiente de aprobación', resolved: 'Resuelto', closed: 'Cerrado', cancelled: 'Cancelado' }
const priorityLabels = { p1: 'P1 · Crítica', p2: 'P2 · Alta', p3: 'P3 · Media', p4: 'P4 · Baja' }
const impactLabels = { single_user: 'Una persona', multiple_users: 'Varias personas', organization: 'Organización' }
const urgencyLabels = { low: 'Baja', medium: 'Media', high: 'Alta' }
const categories: { value: TicketCategory; label: string }[] = [
  { value: 'network.vpn', label: 'VPN y conectividad' }, { value: 'software.application', label: 'Software' },
  { value: 'hardware.endpoint', label: 'Equipo' }, { value: 'access.application', label: 'Acceso' },
]

function useAsync<T>(loader: () => Promise<T>, key = '') {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const loaderRef = useRef(loader)
  loaderRef.current = loader
  const reload = useCallback(() => { setLoading(true); setError(null); void loaderRef.current().then(setData).catch((reason: unknown) => setError(messageOf(reason))).finally(() => setLoading(false)) }, [])
  useEffect(reload, [reload, key])
  return { data, error, loading, reload }
}

function messageOf(reason: unknown) {
  if (reason instanceof ApiError) {
    if (reason.status === 401) return 'Tu sesión terminó. Inicia sesión nuevamente.'
    if (reason.status === 403) return 'No tienes permiso para realizar esta acción.'
    if (reason.status === 412) return 'El ticket cambió en otra sesión. Actualiza antes de continuar.'
    if (reason.status === 503) return 'El servicio está temporalmente ocupado. Intenta nuevamente.'
    return reason.message
  }
  return 'Ocurrió un error inesperado.'
}

export function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [checking, setChecking] = useState(true)
  useEffect(() => { void api.session().then(setSession).catch(() => setSession(null)).finally(() => setChecking(false)) }, [])
  if (checking) return <FullPageStatus label="Comprobando sesión segura…" />
  return <Routes>
    <Route path="/login" element={session ? <Navigate to="/" replace /> : <Login onLogin={setSession} />} />
    <Route path="/*" element={session ? <Shell session={session} onLogout={() => setSession(null)} /> : <Navigate to="/login" replace />} />
  </Routes>
}

function Login({ onLogin }: { onLogin: (session: Session) => void }) {
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError('')
    try { await api.login(loginId, password); onLogin(await api.session()) } catch (reason) { setError(messageOf(reason)) } finally { setBusy(false) }
  }
  return <main className="login-page">
    <section className="login-story" aria-label="Presentación de OpsBridge">
      <Logo large />
      <div><p className="eyebrow light">Operaciones de TI, conectadas</p><h1>De una solicitud a una resolución verificable.</h1><p className="login-copy">OpsBridge ordena tickets, decisiones y evidencia en un espacio local diseñado para equipos responsables.</p></div>
      <div className="trust-row"><ShieldCheck aria-hidden="true" /><span>Sesión local · Datos sintéticos · Control por rol</span></div>
    </section>
    <section className="login-panel">
      <form className="login-card" onSubmit={event => void submit(event)}>
        <div><p className="eyebrow">Acceso seguro</p><h2>Bienvenido de nuevo</h2><p className="muted">Usa una cuenta local creada por el administrador de la demo.</p></div>
        {error && <div className="alert error" role="alert">{error}</div>}
        <label>Identificador<input autoComplete="username" value={loginId} onChange={e => setLoginId(e.target.value)} required /></label>
        <label>Contraseña<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
        <button className="button primary wide" disabled={busy}>{busy ? 'Verificando…' : 'Iniciar sesión'} <ChevronRight aria-hidden="true" /></button>
        <p className="form-note">OpsBridge no incluye credenciales predeterminadas ni transmite datos a servicios externos.</p>
      </form>
    </section>
  </main>
}

const nav = [
  ['/', 'Centro de operaciones', LayoutDashboard], ['/tickets', 'Tickets', TicketCheck], ['/approvals', 'Aprobaciones', ClipboardCheck],
  ['/knowledge', 'Conocimiento', BookOpen], ['/ai-operations', 'AI Operations', Bot], ['/analytics', 'Analítica', BarChart3], ['/settings', 'Configuración', Settings],
] as const

function Shell({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const [open, setOpen] = useState(false)
  const [dark, setDark] = useState(() => localStorage.getItem('opsbridge-theme') === 'dark')
  const location = useLocation()
  useEffect(() => { document.documentElement.dataset.theme = dark ? 'dark' : 'light'; localStorage.setItem('opsbridge-theme', dark ? 'dark' : 'light') }, [dark])
  const logout = async () => { try { await api.logout(session.csrf_token) } finally { onLogout() } }
  return <div className="app-shell">
    <aside className={`sidebar ${open ? 'open' : ''}`}><div className="sidebar-top"><Logo /><button className="icon-button mobile-only" onClick={() => setOpen(false)} aria-label="Cerrar menú"><X /></button></div>
      <nav aria-label="Principal">{nav.map(([path, label, Icon]) => <Link key={path} to={path} onClick={() => setOpen(false)} className={location.pathname === path || (path !== '/' && location.pathname.startsWith(path)) ? 'active' : ''}><Icon aria-hidden="true" /><span>{label}</span>{path === '/ai-operations' && <small>Rules</small>}</Link>)}</nav>
      <div className="sidebar-foot"><div className="mode-card"><span className="status-dot" /><div><strong>Modo local</strong><small>Rules · Sin LLM</small></div></div><button className="sidebar-logout" onClick={() => void logout()}><LogOut /> Cerrar sesión</button></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><button className="icon-button mobile-only" onClick={() => setOpen(true)} aria-label="Abrir menú"><Menu /></button><div className="top-context"><span>OpsBridge /</span><strong>{nav.find(([path]) => path === location.pathname)?.[1] ?? 'Detalle'}</strong></div>
        <div className="top-actions"><button className="icon-button" onClick={() => setDark(v => !v)} aria-label={dark ? 'Usar tema claro' : 'Usar tema oscuro'}>{dark ? <Sun /> : <Moon />}</button><div className="user-chip"><CircleUserRound /><div><strong>{session.display_name}</strong><small>{roleLabel(session.role)}</small></div></div></div></header>
      <div className="page"><Routes>
        <Route index element={<Overview session={session} />} /><Route path="tickets" element={<TicketsPage session={session} />} /><Route path="tickets/:id" element={<TicketDetail session={session} />} />
        <Route path="approvals" element={<ApprovalsPage session={session} />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="ai-operations" element={<AiOperations />} />
        <Route path="analytics" element={<Analytics />} /><Route path="settings" element={<SettingsPage session={session} />} /><Route path="*" element={<NotFound />} />
      </Routes></div>
    </main>
  </div>
}

function Overview({ session }: { session: Session }) {
  const { data, error, loading, reload } = useAsync(async () => {
    const [summary, recent] = await Promise.all([api.ticketSummary(), api.listTickets('?page_size=5')])
    return { summary, recent: recent.data }
  })
  const summary = data?.summary
  const recent = data?.recent ?? []
  const statusCounts = Object.fromEntries(summary?.by_status.map(item => [item.name, item.value]) ?? [])
  const priorityCounts = Object.fromEntries(summary?.by_priority.map(item => [item.name, item.value]) ?? [])
  const byStatus = Object.entries(statusLabels).map(([name, label]) => ({ name: label, value: statusCounts[name] ?? 0 }))
  const byPriority = ['p1', 'p2', 'p3', 'p4'].map(name => ({ name: name.toUpperCase(), value: priorityCounts[name] ?? 0 }))
  const active = ['triaged', 'in_progress', 'waiting_requester', 'waiting_approval'].reduce((total, name) => total + (statusCounts[name] ?? 0), 0)
  const highPriority = (priorityCounts.p1 ?? 0) + (priorityCounts.p2 ?? 0)
  const resolved = (statusCounts.resolved ?? 0) + (statusCounts.closed ?? 0)
  return <><PageHeader eyebrow="Operations center" title={`Hola, ${session.display_name.split(' ')[0]}`} description="Estado operativo calculado a partir de los tickets que tu rol puede consultar." action={<Link to="/tickets?new=1" className="button primary"><Plus /> Crear ticket</Link>} />
    {error && <ErrorState text={error} retry={reload} />}{loading ? <SkeletonGrid /> : <>
      <section className="metrics" aria-label="Resumen de tickets"><Metric label="Tickets visibles" value={summary?.total ?? 0} detail="Alcance completo según tu rol" tone="indigo" /><Metric label="En atención" value={active} detail="Trabajo activo" tone="teal" /><Metric label="Prioridad P1/P2" value={highPriority} detail="Requieren atención" tone="coral" /><Metric label="Resueltos" value={resolved} detail="Ciclo avanzado" tone="sky" /></section>
      <section className="dashboard-grid"><article className="card chart-card"><CardTitle title="Distribución por estado" subtitle="Todo el alcance autorizado" /><div className="chart-wrap"><Suspense fallback={<ChartFallback />}><StatusBarChart data={byStatus} /></Suspense></div></article>
      <article className="card chart-card compact"><CardTitle title="Prioridad" subtitle="Volumen completo, no rendimiento" /><div className="chart-wrap"><Suspense fallback={<ChartFallback />}><PriorityPieChart data={byPriority} /></Suspense></div><div className="legend">{byPriority.map((p,i) => <span key={p.name}><i style={{background:['#ff8b78','#f0a54a','#46b8f5','#13b8a6'][i]}} />{p.name}: {p.value}</span>)}</div></article>
      <article className="card recent-card"><CardTitle title="Actividad reciente" subtitle="Últimos tickets actualizados" /><div className="activity-list">{recent.map(t => <Link to={`/tickets/${t.id}`} key={t.id}><span className={`priority ${t.priority}`}>{t.priority.toUpperCase()}</span><div><strong>{t.title}</strong><small>{t.key} · {statusLabels[t.status]}</small></div><ChevronRight /></Link>)}{!recent.length && <EmptyState title="Sin actividad todavía" text="Crea el primer ticket para iniciar el recorrido operativo." />}</div></article></section>
    </>}</>
}

function TicketsPage({ session }: { session: Session }) {
  const navigate = useNavigate(); const location = useLocation()
  const [query, setQuery] = useState(''); const [status, setStatus] = useState(''); const [showCreate, setShowCreate] = useState(new URLSearchParams(location.search).has('new'))
  const [pageIndex, setPageIndex] = useState(0); const [cursors, setCursors] = useState<(string | null)[]>([null])
  const resetPagination = () => { setPageIndex(0); setCursors([null]) }
  const params = useMemo(() => { const p = new URLSearchParams({ page_size: '25' }); if(query)p.set('query',query); if(status)p.set('status',status); const cursor=cursors[pageIndex]; if(cursor)p.set('cursor',cursor); return `?${p}` }, [query,status,pageIndex,cursors])
  const { data, error, loading, reload } = useAsync(() => api.listTickets(params), params)
  return <><PageHeader eyebrow="Ticket workspace" title="Tickets" description="Busca, filtra y trabaja con solicitudes dentro de los permisos efectivos de tu sesión." action={session.role !== 'approver' ? <button className="button primary" onClick={() => setShowCreate(true)}><Plus /> Nuevo ticket</button> : undefined} />
    <section className="card table-card"><div className="table-tools"><label className="search-field"><Search /><span className="sr-only">Buscar tickets</span><input placeholder="Buscar por título o código…" value={query} onChange={e => { setQuery(e.target.value); resetPagination() }} /></label><label className="filter-field"><ListFilter /><span className="sr-only">Filtrar por estado</span><select value={status} onChange={e => { setStatus(e.target.value); resetPagination() }}><option value="">Todos los estados</option>{Object.entries(statusLabels).map(([v,l]) => <option key={v} value={v}>{l}</option>)}</select></label><button className="icon-button" onClick={reload} aria-label="Actualizar"><RefreshCw /></button></div>
    {error ? <ErrorState text={error} retry={reload} /> : loading ? <TableSkeleton /> : data?.data.length ? <><div className="table-scroll" tabIndex={0} aria-label="Tabla desplazable de tickets"><table><thead><tr><th>Ticket</th><th>Estado</th><th>Prioridad</th><th>Categoría</th><th>Actualizado</th><th><span className="sr-only">Abrir</span></th></tr></thead><tbody>{data.data.map(t => <tr key={t.id} onClick={() => navigate(`/tickets/${t.id}`)}><td><strong>{t.title}</strong><small>{t.key}</small></td><td><StatusBadge status={t.status} /></td><td><span className={`priority ${t.priority}`}>{priorityLabels[t.priority]}</span></td><td>{categories.find(c => c.value === t.category)?.label}</td><td>{dateTime(t.updated_at)}</td><td><Link aria-label={`Abrir ${t.key}`} to={`/tickets/${t.id}`}><ChevronRight /></Link></td></tr>)}</tbody></table></div><nav className="pagination" aria-label="Paginación de tickets"><button className="button ghost" disabled={pageIndex===0} onClick={()=>setPageIndex(index=>Math.max(0,index-1))}>Anterior</button><span>Página {pageIndex+1}</span><button className="button ghost" disabled={!data.meta.has_more||!data.meta.next_cursor} onClick={()=>{if(!data.meta.next_cursor)return;setCursors(current=>{const next=[...current];next[pageIndex+1]=data.meta.next_cursor;return next});setPageIndex(index=>index+1)}}>Siguiente</button></nav></> : <EmptyState title="No hay resultados" text="Ajusta los filtros o crea una solicitud nueva." />}</section>
    {showCreate && <CreateDialog session={session} close={() => setShowCreate(false)} created={ticket => { setShowCreate(false); void navigate(`/tickets/${ticket.id}`) }} />}</>
}

function CreateDialog({ session, close, created }: { session: Session; close: () => void; created: (ticket: Ticket) => void }) {
  const [form, setForm] = useState({ title:'', description:'', category:'network.vpn' as TicketCategory, impact:'single_user', urgency:'medium' }); const [error,setError]=useState(''); const [busy,setBusy]=useState(false); const dialogRef=useRef<HTMLDivElement>(null); const titleRef=useRef<HTMLInputElement>(null); const idempotencyKey=useRef(crypto.randomUUID())
  useEffect(()=>{const previous=document.activeElement instanceof HTMLElement?document.activeElement:null;titleRef.current?.focus();const keydown=(event:KeyboardEvent)=>{if(event.key==='Escape'){event.preventDefault();close();return}if(event.key!=='Tab'||!dialogRef.current)return;const focusable=Array.from(dialogRef.current.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])')).filter(item=>!item.hasAttribute('hidden'));const first=focusable[0];const last=focusable[focusable.length-1];if(!first||!last)return;if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}};document.addEventListener('keydown',keydown);return()=>{document.removeEventListener('keydown',keydown);previous?.focus()}},[close])
  const submit = async (e: FormEvent) => { e.preventDefault(); setBusy(true); setError(''); try { created(await api.createTicket(session.csrf_token, form, idempotencyKey.current)) } catch(reason){setError(messageOf(reason))} finally{setBusy(false)} }
  return <div className="modal-backdrop" role="presentation"><div ref={dialogRef} className="modal" role="dialog" aria-modal="true" aria-labelledby="create-title" aria-describedby="create-description"><div className="modal-head"><div><p className="eyebrow">Nueva solicitud</p><h2 id="create-title">Crear ticket</h2><p id="create-description" className="sr-only">Completa los datos sintéticos del incidente. Escape cierra este diálogo.</p></div><button type="button" className="icon-button" onClick={close} aria-label="Cerrar"><X /></button></div><form onSubmit={e => void submit(e)}>{error && <div className="alert error" role="alert">{error}</div>}<label>Título<input ref={titleRef} minLength={5} maxLength={160} required value={form.title} onChange={e=>setForm({...form,title:e.target.value})} /></label><label>Descripción<textarea minLength={20} maxLength={4000} required rows={6} value={form.description} onChange={e=>setForm({...form,description:e.target.value})} /></label><div className="form-grid"><label>Categoría<select value={form.category} onChange={e=>setForm({...form,category:e.target.value as TicketCategory})}>{categories.map(c=><option key={c.value} value={c.value}>{c.label}</option>)}</select></label><label>Impacto<select value={form.impact} onChange={e=>setForm({...form,impact:e.target.value})}><option value="single_user">Una persona</option><option value="multiple_users">Varias personas</option><option value="organization">Organización</option></select></label><label>Urgencia<select value={form.urgency} onChange={e=>setForm({...form,urgency:e.target.value})}><option value="low">Baja</option><option value="medium">Media</option><option value="high">Alta</option></select></label></div><div className="modal-actions"><button type="button" className="button ghost" onClick={close}>Cancelar</button><button className="button primary" disabled={busy}>{busy?'Creando…':'Crear ticket'}</button></div></form></div></div>
}

function TicketDetail({ session }: { session: Session }) {
  const { id = '' } = useParams(); const [conflict,setConflict]=useState(''); const [proposalNotice,setProposalNotice]=useState(''); const [selectedTarget,setSelectedTarget]=useState<TicketStatus|null>(null); const [transitionData,setTransitionData]=useState({reason:'',resolution_summary:'',requester_response_received:false,requester_confirmed:false}); const { data,error,loading,reload }=useAsync(async()=>{const [detail,timeline,transitionOptions]=await Promise.all([api.getTicket(id),api.timeline(id),api.transitionOptions(id)]); return {...detail,timeline,transitionOptions}},id)
  const transition = async (e: FormEvent) => { e.preventDefault(); if(!data||!selectedTarget)return; setConflict(''); try{await api.transitionTicket(session.csrf_token,id,data.etag,{target:selectedTarget,...transitionData});setSelectedTarget(null);reload()}catch(reason){setConflict(messageOf(reason))} }
  if(loading)return <FullPageStatus label="Cargando ticket…" />; if(error||!data)return <ErrorState text={error??'Ticket no encontrado.'} retry={reload} />
  const t=data.ticket; const selectedOption=data.transitionOptions.find(option=>option.target===selectedTarget)
  return <><div className="detail-back"><Link to="/tickets">← Volver a tickets</Link></div><PageHeader eyebrow={t.key} title={t.title} description={`${categories.find(c=>c.value===t.category)?.label} · Actualizado ${dateTime(t.updated_at)}`} action={<StatusBadge status={t.status} />} />
  {conflict&&<div className="alert warning" role="alert">{conflict} <button onClick={reload}>Actualizar</button></div>}
  <section className="detail-grid"><article className="card detail-main"><div className="detail-section"><h2>Descripción</h2><p>{t.description}</p></div><div className="metadata"><Meta label="Prioridad" value={priorityLabels[t.priority]} /><Meta label="Impacto" value={impactLabels[t.impact]} /><Meta label="Urgencia" value={urgencyLabels[t.urgency]} /><Meta label="Versión" value={`v${t.version}`} /></div>{data.transitionOptions.length>0&&<div className="action-strip"><div><strong>Siguiente acción</strong><small>Opciones autorizadas por la API para esta sesión.</small></div>{data.transitionOptions.map(option=><button key={option.target} className="button secondary" onClick={()=>setSelectedTarget(option.target)}>{statusLabels[option.target]}</button>)}</div>}{selectedOption&&<form className="transition-form" onSubmit={e=>void transition(e)}><h3>Confirmar: {statusLabels[selectedOption.target]}</h3>{selectedOption.required_fields.includes('reason')&&<label>Motivo<textarea required value={transitionData.reason} onChange={e=>setTransitionData({...transitionData,reason:e.target.value})}/></label>}{selectedOption.required_fields.includes('resolution_summary')&&<label>Resumen de resolución<textarea required value={transitionData.resolution_summary} onChange={e=>setTransitionData({...transitionData,resolution_summary:e.target.value})}/></label>}{selectedOption.required_fields.includes('requester_response_received')&&<label className="checkbox-field"><input type="checkbox" required checked={transitionData.requester_response_received} onChange={e=>setTransitionData({...transitionData,requester_response_received:e.target.checked})}/> Confirmo que respondí a la solicitud</label>}{selectedOption.required_fields.includes('requester_confirmed')&&<label className="checkbox-field"><input type="checkbox" required checked={transitionData.requester_confirmed} onChange={e=>setTransitionData({...transitionData,requester_confirmed:e.target.checked})}/> Confirmo que la solución funciona</label>}<div className="modal-actions"><button type="button" className="button ghost" onClick={()=>setSelectedTarget(null)}>Cancelar</button><button className="button primary">Confirmar transición</button></div></form>}</article>
  <aside className="card timeline"><CardTitle title="Línea de tiempo" subtitle={data.timeline.hasMore?`Mostrando los primeros ${data.timeline.events.length} eventos`:`${data.timeline.events.length} eventos persistidos`} />{data.timeline.events.map((event,i)=><TimelineItem key={`${event.revision}-${i}`} event={event} />)}</aside>
  <article className="card evidence-card"><div className="feature-icon"><LifeBuoy /></div><div><h2>Diagnóstico y evidencia</h2><p>Consulta el hub de conocimiento para recuperar procedimientos con citas persistidas.</p>{proposalNotice&&<small>{proposalNotice}</small>}</div>{session.role==='technician'&&t.category==='network.vpn'&&t.status==='in_progress'&&t.assignee_id===session.user_id?<button className="button primary" onClick={()=>void api.proposeVpnReset(session.csrf_token,t.id,data.etag,'DEMO-VPN-001').then(()=>setProposalNotice('Propuesta creada; requiere aprobación independiente.')).catch(reason=>setConflict(messageOf(reason)))}>Proponer reset sintético</button>:<Link className="button ghost" to="/knowledge">Buscar evidencia</Link>}</article></section></>
}

function KnowledgePage(){const[query,setQuery]=useState('vpn');const[result,setResult]=useState<Awaited<ReturnType<typeof api.searchKnowledge>>|null>(null);const[error,setError]=useState('');const[busy,setBusy]=useState(false);const submit=async(e:FormEvent)=>{e.preventDefault();setBusy(true);setError('');try{setResult(await api.searchKnowledge(query))}catch(reason){setError(messageOf(reason))}finally{setBusy(false)}};return <><PageHeader eyebrow="Knowledge hub" title="Evidencia local con citas" description="Recuperación léxica FTS5 limitada por rol. El contenido documental se trata como datos no confiables, nunca como instrucciones."/><section className="card knowledge-panel"><form className="knowledge-search" onSubmit={e=>void submit(e)}><label className="search-field"><Search/><span className="sr-only">Consulta</span><input minLength={1} maxLength={200} value={query} onChange={e=>setQuery(e.target.value)} placeholder="Ej. VPN bloqueada"/></label><button className="button primary" disabled={busy}>{busy?'Buscando…':'Buscar'}</button></form>{error&&<div className="alert error">{error}</div>}{result&&<div className="citation-list">{result.abstained?<EmptyState title="Sin evidencia suficiente" text="La búsqueda se abstuvo; ajusta la consulta o escala al equipo responsable."/>:result.citations.map(c=><article key={c.chunk_id} className="citation"><small>{c.document_code} · v{c.document_version}</small><h2>{c.heading}</h2><p>{c.content}</p><span>Fuente: {c.document_title} · score {c.score.toFixed(3)}</span></article>)}</div>}</section></>}

function ApprovalsPage({session}:{session:Session}){const{data,error,loading,reload}=useAsync(()=>api.listProposals());const[notice,setNotice]=useState('');const act=async(item:ActionProposal,action:'approve'|'reject'|'execute')=>{setNotice('');try{if(action==='execute'){const execution=await api.executeProposal(session.csrf_token,item.id);const state=typeof execution.result.current_state==='string'?execution.result.current_state:'desconocido';const count=typeof execution.result.reset_count==='number'?execution.result.reset_count:'?';setNotice(`Simulación completada: estado ${state} · reset #${count}.`)}else{await api.decideProposal(session.csrf_token,item.id,action,action==='approve'?'Evidencia sintética validada.':'Propuesta rechazada durante revisión.');setNotice('Decisión registrada correctamente.')}reload()}catch(reason){setNotice(messageOf(reason))}};return <><PageHeader eyebrow="Control humano" title="Aprobaciones gobernadas" description="Separación de funciones, expiración, hash de argumentos y ejecución exactamente una vez."/>{notice&&<div className="alert info" role="status">{notice}</div>}<section className="card proposal-list">{error?<ErrorState text={error} retry={reload}/>:loading?<TableSkeleton/>:data?.length?data.map(item=><article className="proposal" key={item.id}><div><small>{item.action_type} · {item.source_mode}</small><h2>{typeof item.arguments.identity_code==='string'?item.arguments.identity_code:'Identidad sintética'}</h2><p>Ticket v{item.ticket_version} · expira {dateTime(item.expires_at)}</p><code>{item.arguments_hash.slice(0,16)}…</code></div><strong className="proposal-status">{item.status.replaceAll('_',' ')}</strong><div className="proposal-actions">{session.role==='approver'&&item.status==='pending_approval'&&<><button className="button primary" onClick={()=>void act(item,'approve')}>Aprobar</button><button className="button ghost" onClick={()=>void act(item,'reject')}>Rechazar</button></>}{session.role==='technician'&&item.status==='approved'&&<button className="button primary" onClick={()=>void act(item,'execute')}>Ejecutar simulador</button>}</div></article>):<EmptyState title="Sin propuestas visibles" text="Las propuestas válidas aparecerán aquí según el rol de la sesión."/>}</section></>}

function AiOperations(){const{data,error,loading,reload}=useAsync(()=>api.aiStatus());return <><PageHeader eyebrow="AI operations" title="Modos verificables" description="Estado real de cada capacidad; las reglas deterministas no se presentan como inteligencia generativa."/>{error?<ErrorState text={error} retry={reload}/>:loading?<SkeletonGrid/>:<section className="settings-grid"><ModeCard title="Rules" state={data?.rules_available?'Disponible':'No disponible'} text="Política determinista y allowlist para propuestas."/><ModeCard title="Retrieval" state="Disponible" text={data?.retrieval_mode??'sqlite_fts5_lexical'}/><ModeCard title="LLM local" state="Pendiente" text={`${data?.provider??'ollama'} · ${data?.status??'LOCAL_LLM_PENDING'}`}/></section>}</>}

function ModeCard({title,state,text}:{title:string;state:string;text:string}){return <article className="card setting-card"><Bot/><div><h2>{title}</h2><p>{text}</p></div><strong className="mode-state">{state}</strong></article>}

function Analytics(){const {data,error,loading,reload}=useAsync(()=>api.ticketSummary());const days=(data?.created_by_day??[]).map(item=>({date:new Date(`${item.day}T00:00:00Z`).toLocaleDateString('es-CR',{month:'short',day:'numeric',timeZone:'UTC'}),total:item.value}));return <><PageHeader eyebrow="Analítica operativa" title="Volumen verificable" description="Indicadores agregados sobre todo el alcance autorizado. No representan SLA, ahorro ni precisión de IA." />{error?<ErrorState text={error} retry={reload}/>:loading?<SkeletonGrid/>:<section className="card chart-card full"><CardTitle title="Tickets creados por fecha" subtitle={`${data?.total??0} registros autorizados`} /><div className="chart-wrap tall"><Suspense fallback={<ChartFallback />}><DailyVolumeChart data={days}/></Suspense></div></section>}</>}

function SettingsPage({session}:{session:Session}){const {data,error}=useAsync(()=>api.health());return <><PageHeader eyebrow="Configuración y privacidad" title="Estado local" description="Información no sensible del entorno actual."/><section className="settings-grid"><article className="card setting-card"><Activity/><div><h2>API y base de datos</h2><p>{error?'No disponible':data?.status==='ready'?'Operativa':'Comprobando…'}</p></div><span className={`health ${error?'off':''}`}/></article><article className="card setting-card"><ShieldCheck/><div><h2>Sesión</h2><p>{roleLabel(session.role)} · expira {dateTime(session.expires_at)}</p></div></article><article className="card setting-card"><Bot/><div><h2>Modo de asistencia</h2><p>Rules · LLM local no verificado</p></div></article></section><article className="card about-card"><Logo/><div><h2>OpsBridge AI</h2><p>Plataforma local de portafolio. Los datos de demostración son sintéticos; no está preparada para exposición pública ni operación empresarial real.</p></div></article></>}

function Logo({large=false}:{large?:boolean}){return <div className={`logo ${large?'large':''}`}><svg viewBox="0 0 64 64" aria-hidden="true"><path d="M12 42V28m40 14V28M12 32c11-15 29-15 40 0M20 42h24"/><circle cx="12" cy="25" r="4"/><circle cx="52" cy="25" r="4"/></svg><div><strong>OpsBridge</strong><span>AI</span><small>Intelligent IT Operations</small></div></div>}
function PageHeader({eyebrow,title,description,action}:{eyebrow:string;title:string;description:string;action?:ReactNode}){return <header className="page-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>{action&&<div>{action}</div>}</header>}
function Metric({label,value,detail,tone}:{label:string;value:number;detail:string;tone:string}){return <article className={`metric ${tone}`}><div><span>{label}</span><strong>{value}</strong><small>{detail}</small></div><Activity aria-hidden="true"/></article>}
function CardTitle({title,subtitle}:{title:string;subtitle:string}){return <div className="card-title"><div><h2>{title}</h2><p>{subtitle}</p></div></div>}
function StatusBadge({status}:{status:TicketStatus}){return <span className={`status-badge ${status}`}><i/>{statusLabels[status]}</span>}
function Meta({label,value}:{label:string;value:string}){return <div><small>{label}</small><strong>{value}</strong></div>}
function TimelineItem({event}:{event:TicketEvent}){return <div className="timeline-item"><span><CheckCircle2/></span><div><strong>{event.type.replaceAll('_',' ')}</strong><small>{roleLabel(event.actor_role)} · {dateTime(event.occurred_at)}</small></div><em>#{event.revision}</em></div>}
function ComingSoon({icon,title,text}:{icon:ReactNode;title:string;text:string}){return <section className="coming card"><div className="feature-icon">{icon}</div><p className="eyebrow">Capacidad gobernada</p><h1>{title}</h1><p>{text}</p><div className="alert info">Esta pantalla está deliberadamente deshabilitada hasta que exista un contrato backend probado.</div></section>}
function EmptyState({title,text}:{title:string;text:string}){return <div className="empty"><TicketCheck/><strong>{title}</strong><p>{text}</p></div>}
function ErrorState({text,retry}:{text:string;retry:()=>void}){return <div className="empty error-state" role="alert"><LifeBuoy/><strong>No se pudo cargar</strong><p>{text}</p><button className="button secondary" onClick={retry}><RefreshCw/>Reintentar</button></div>}
function SkeletonGrid(){return <div className="metrics">{[1,2,3,4].map(i=><div className="skeleton metric" key={i}/>)}</div>}
function TableSkeleton(){return <div className="table-skeleton">{[1,2,3,4,5].map(i=><div className="skeleton" key={i}/>)}</div>}
function ChartFallback(){return <div className="skeleton chart-fallback" aria-label="Cargando gráfico" />}
function FullPageStatus({label}:{label:string}){return <div className="full-status"><span className="spinner"/><p>{label}</p></div>}
function NotFound(){return <ComingSoon icon={<Search/>} title="Página no encontrada" text="La ruta solicitada no forma parte de esta versión de OpsBridge."/>}
function roleLabel(role:string){return ({requester:'Solicitante',technician:'Técnico',approver:'Aprobador'} as Record<string,string>)[role]??role}
function dateTime(value:string){return new Intl.DateTimeFormat('es-CR',{dateStyle:'medium',timeStyle:'short'}).format(new Date(value))}
