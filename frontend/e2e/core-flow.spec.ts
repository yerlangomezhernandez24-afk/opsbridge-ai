import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Browser, type Page } from '@playwright/test'
import path from 'node:path'

const password = process.env.OPSBRIDGE_E2E_PASSWORD
const screenshots = path.resolve(process.cwd(), '../docs/screenshots')
const workflowTitle = 'Incidente VPN reproducible auditoría bloqueantes'

async function login(page: Page, loginId = 'demo.requester') {
  if (!password) throw new Error('OPSBRIDGE_E2E_PASSWORD is required')
  await page.goto('/login')
  await page.getByLabel('Identificador', { exact: true }).fill(loginId)
  await page.getByLabel('Contraseña', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Iniciar sesión' }).click()
  await expect(page).toHaveURL('http://127.0.0.1:5173/')
}

async function isolatedLogin(browser: Browser, loginId: string) {
  const context = await browser.newContext()
  const page = await context.newPage()
  await login(page, loginId)
  return { context, page }
}

async function openWorkflowTicket(page: Page) {
  await page.getByRole('link', { name: 'Tickets', exact: true }).click()
  await page.getByPlaceholder('Buscar por título o código…').fill(workflowTitle)
  await page.getByText(workflowTitle, { exact: true }).first().click()
}

test('requester completes the real ticket workflow with accessible responsive UI', async ({ page }) => {
  await login(page)
  await expect(page.getByRole('heading', { name: /Hola, Sofía/ })).toBeVisible()
  const summary = await page.evaluate(() => fetch('/api/v1/tickets/summary').then(response => response.json()) as Promise<{ data: { total: number; by_priority: { name: string; value: number }[] } }>)
  await expect(page.locator('.metrics .metric').first().locator('strong')).toHaveText(String(summary.data.total))
  await page.locator('.recharts-surface').first().waitFor({ state: 'visible' })
  await page.waitForTimeout(1200)
  const barHeights = await page.locator('.recharts-bar-rectangle path').evaluateAll(paths => paths.map(path => (path as SVGGraphicsElement).getBBox().height))
  expect(barHeights.some(height => height > 0)).toBe(true)
  const positivePriorities = summary.data.by_priority.filter(item => item.value > 0).length
  expect(await page.locator('.recharts-pie-sector path').count()).toBe(positivePriorities)
  await page.screenshot({ path: path.join(screenshots, 'audit-chatgpt-dashboard-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('button', { name: 'Abrir menú' })).toBeVisible()
  await page.screenshot({ path: path.join(screenshots, 'audit-chatgpt-dashboard-mobile.png'), fullPage: true })
  await page.setViewportSize({ width: 1366, height: 768 })

  await page.getByRole('link', { name: 'Tickets', exact: true }).click()
  const trigger = page.getByRole('button', { name: 'Nuevo ticket' })
  await trigger.click()
  let dialog = page.getByRole('dialog')
  await expect(dialog.getByLabel('Título', { exact: true })).toBeFocused()
  await dialog.getByRole('button', { name: 'Cerrar' }).focus()
  await page.keyboard.press('Shift+Tab')
  await expect(dialog.getByRole('button', { name: 'Crear ticket' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(trigger).toBeFocused()
  await trigger.click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Título', { exact: true }).fill(workflowTitle)
  await dialog.getByLabel('Descripción', { exact: true }).fill('La VPN sintética pierde conectividad durante la prueba integral del flujo web local.')
  await dialog.locator('select').nth(1).selectOption('multiple_users')
  await dialog.locator('select').nth(2).selectOption('high')
  await dialog.getByRole('button', { name: 'Crear ticket' }).click()

  await expect(page).toHaveURL(/\/tickets\/[0-9a-f-]+/)
  await expect(page.getByRole('heading', { name: workflowTitle })).toBeVisible()
  await expect(page.getByText('Varias personas')).toBeVisible()
  await page.screenshot({ path: path.join(screenshots, 'phase3-ticket-detail-desktop.png'), fullPage: true })

  const accessibility = await new AxeBuilder({ page }).analyze()
  expect(accessibility.violations.filter(item => ['serious', 'critical'].includes(item.impact ?? ''))).toEqual([])

  for (const viewport of [
    { width: 360, height: 800 },
    { width: 390, height: 844 },
    { width: 768, height: 1024 },
    { width: 1366, height: 768 },
    { width: 1920, height: 1080 },
  ]) {
    await page.setViewportSize(viewport)
    await expect(page.getByRole('heading', { name: workflowTitle })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    if (viewport.width === 390) {
      await expect(page.getByRole('button', { name: 'Abrir menú' })).toBeVisible()
      await page.screenshot({ path: path.join(screenshots, 'phase3-ticket-detail-mobile.png'), fullPage: true })
    }
  }
})

test('technician can open and advance a persisted requester ticket', async ({ page }) => {
  await login(page, 'demo.technician')
  await openWorkflowTicket(page)
  await expect(page.getByRole('heading', { name: workflowTitle })).toBeVisible()
  await page.getByRole('button', { name: 'Clasificado' }).click()
  await page.getByRole('button', { name: 'Confirmar transición' }).click()
  await expect(page.locator('.status-badge')).toContainText('Clasificado')
  await page.getByRole('button', { name: 'En progreso' }).click()
  await page.getByRole('button', { name: 'Confirmar transición' }).click()
  await expect(page.locator('.status-badge')).toContainText('En progreso')
  await expect(page.getByText('TicketStatusChanged').first()).toBeVisible()
  await page.screenshot({ path: path.join(screenshots, 'phase3-technician-workspace.png'), fullPage: true })
})

test('governed knowledge, approval, and synthetic execution complete end to end', async ({ page }) => {
  await login(page, 'demo.technician')
  await page.getByRole('link', { name: 'Conocimiento' }).click()
  await page.getByLabel('Consulta').fill('vpn sesion bloqueada')
  await page.getByRole('button', { name: 'Buscar' }).click()
  await expect(page.getByText(/KB-VPN-001/).first()).toBeVisible()
  await page.screenshot({ path: path.join(screenshots, 'phase4-knowledge-desktop.png'), fullPage: true })

  await openWorkflowTicket(page)
  await page.getByRole('button', { name: 'Proponer reset sintético' }).click()
  await expect(page.getByText('Propuesta creada; requiere aprobación independiente.')).toBeVisible()
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()

  await login(page, 'demo.approver')
  await page.getByRole('link', { name: 'Aprobaciones' }).click()
  await page.screenshot({ path: path.join(screenshots, 'phase4-approval-desktop.png'), fullPage: true })
  await page.getByRole('button', { name: 'Aprobar' }).first().click()
  await expect(page.getByText('Decisión registrada correctamente.')).toBeVisible()
  const repeatedDecision = await page.evaluate(async () => {
    const session = await fetch('/api/v1/auth/session').then(response => response.json()) as { csrf_token: string }
    const proposals = await fetch('/api/v1/approval-requests').then(response => response.json()) as { data: { id: string; status: string }[] }
    const proposal = proposals.data.find(item => item.status === 'approved')
    if (!proposal) throw new Error('Approved proposal not found')
    return fetch(`/api/v1/approval-requests/${proposal.id}/decisions`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token },
      body: JSON.stringify({ decision: 'approve', reason: 'Replay must be rejected.' }),
    }).then(response => response.status)
  })
  expect(repeatedDecision).toBe(409)
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()

  await login(page, 'demo.technician')
  await page.getByRole('link', { name: 'Aprobaciones' }).click()
  await page.getByRole('button', { name: 'Ejecutar simulador' }).first().click()
  await expect(page.getByText(/Simulación completada: estado active · reset #[1-9]\d*/)).toBeVisible()
  await expect(page.getByText('executed').first()).toBeVisible()
  const repeatedExecution = await page.evaluate(async () => {
    const session = await fetch('/api/v1/auth/session').then(response => response.json()) as { csrf_token: string }
    const proposals = await fetch('/api/v1/approval-requests').then(response => response.json()) as { data: { id: string; status: string }[] }
    const proposal = proposals.data.find(item => item.status === 'executed')
    if (!proposal) throw new Error('Executed proposal not found')
    return fetch(`/api/v1/approval-requests/${proposal.id}/executions`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token },
    }).then(response => response.status)
  })
  expect(repeatedExecution).toBe(409)
  await page.screenshot({ path: path.join(screenshots, 'phase4-execution-desktop.png'), fullPage: true })

  await openWorkflowTicket(page)
  await page.getByRole('button', { name: 'Resuelto' }).click()
  await page.getByLabel('Resumen de resolución').fill('La sesión VPN sintética fue restablecida y verificada sin operar sistemas reales.')
  await page.getByRole('button', { name: 'Confirmar transición' }).click()
  await expect(page.locator('.status-badge')).toContainText('Resuelto')
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()

  await login(page)
  await openWorkflowTicket(page)
  await page.getByRole('button', { name: 'Cerrado' }).click()
  await page.getByLabel('Confirmo que la solución funciona').check()
  await page.getByRole('button', { name: 'Confirmar transición' }).click()
  await expect(page.locator('.status-badge')).toContainText('Cerrado')
  await page.screenshot({ path: path.join(screenshots, 'audit-blockers-ticket-closed-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: path.join(screenshots, 'audit-blockers-ticket-closed-mobile.png'), fullPage: true })
})

test('resource authorization, CSRF, ETag, and idempotency reject unsafe browser flows', async ({ page, browser }) => {
  await login(page)
  await page.getByRole('link', { name: 'Tickets', exact: true }).click()
  await page.getByRole('button', { name: 'Nuevo ticket' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Título', { exact: true }).fill('VPN exclusiva para prueba de autorización')
  await dialog.getByLabel('Descripción', { exact: true }).fill('Este incidente sintético valida IDOR, CSRF, ETag e idempotencia desde navegador real.')
  await dialog.getByRole('button', { name: 'Crear ticket' }).click()
  await expect(page).toHaveURL(/\/tickets\/[0-9a-f-]+/)
  const ticketUrl = page.url()

  const other = await isolatedLogin(browser, 'demo.requester2')
  await other.page.goto(ticketUrl)
  await expect(other.page.getByRole('heading', { name: 'VPN exclusiva para prueba de autorización' })).toHaveCount(0)
  await expect(other.page.getByRole('alert')).toContainText('No se pudo cargar')
  await other.context.close()

  const first = await isolatedLogin(browser, 'demo.technician')
  const second = await isolatedLogin(browser, 'demo.technician')
  await Promise.all([first.page.goto(ticketUrl), second.page.goto(ticketUrl)])
  await expect(first.page.getByRole('heading', { name: 'VPN exclusiva para prueba de autorización' })).toBeVisible()
  await expect(second.page.getByRole('heading', { name: 'VPN exclusiva para prueba de autorización' })).toBeVisible()
  await first.page.getByRole('button', { name: 'Clasificado' }).click()
  await first.page.getByRole('button', { name: 'Confirmar transición' }).click()
  await expect(first.page.locator('.status-badge')).toContainText('Clasificado')
  await second.page.getByRole('button', { name: 'Clasificado' }).click()
  await second.page.getByRole('button', { name: 'Confirmar transición' }).click()
  await expect(second.page.getByRole('alert')).toContainText('cambió en otra sesión')

  const csrfStatus = await first.page.evaluate(async () => {
    const ticketId = location.pathname.split('/').at(-1)
    return fetch(`/api/v1/tickets/${ticketId}/transitions`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'If-Match': '"2"' },
      body: JSON.stringify({ target: 'in_progress' }),
    }).then(response => response.status)
  })
  expect(csrfStatus).toBe(403)
  await first.context.close()
  await second.context.close()

  const idempotency = await page.evaluate(async () => {
    const session = await fetch('/api/v1/auth/session').then(response => response.json()) as { csrf_token: string }
    const key = crypto.randomUUID()
    const payload = { title: 'Replay idempotente desde navegador', description: 'Solicitud sintética repetida con la misma clave y exactamente el mismo contenido.', category: 'network.vpn', impact: 'single_user', urgency: 'medium' }
    const send = (body: typeof payload) => fetch('/api/v1/tickets', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token, 'Idempotency-Key': key }, body: JSON.stringify(body) })
    const firstResponse = await send(payload)
    const firstBody = await firstResponse.json() as { data: { id: string } }
    const replayResponse = await send(payload)
    const replayBody = await replayResponse.json() as { data: { id: string } }
    const conflictResponse = await send({ ...payload, description: 'Contenido sintético diferente que debe producir conflicto de idempotencia.' })
    return { first: firstResponse.status, replay: replayResponse.status, conflict: conflictResponse.status, sameId: firstBody.data.id === replayBody.data.id }
  })
  expect(idempotency).toEqual({ first: 201, replay: 201, conflict: 409, sameId: true })
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await expect(page).toHaveURL(/\/login$/)
})
