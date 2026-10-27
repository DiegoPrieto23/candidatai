import createClient from 'openapi-fetch'
import { i18n } from '@/lib/i18n'
import type { components, paths } from './schema'

export type Schemas = components['schemas']
export type Stage = Schemas['Stage']
export type MailSourceView = Schemas['MailSourceView']
export type MailSourceInput = Schemas['MailSourceInput']
export type MailTestResult = Schemas['MailTestResult']
export type JobRow = Schemas['JobRow']
export type JobView = Schemas['JobView']
export type JobSignals = Schemas['JobSignals']
export type LivenessView = Schemas['LivenessView']
export type EventOut = Schemas['EventOut']
export type StatusReport = Schemas['StatusReport']
export type AddJobResult = Schemas['AddJobResult']
export type ErrorDetail = Schemas['ErrorDetail']
export type MatchView = Schemas['MatchView']
export type TriageItem = Schemas['TriageItem']
export type TriageQueue = Schemas['TriageQueue']
export type DiscardReason = NonNullable<Schemas['AddUserEventBody']['reason']>
export type JobCv = Schemas['JobCv']
export type CvView = Schemas['CvView']
export type RenderResult = Schemas['RenderResult']
export type CvRenderOptions = Schemas['CvRenderOptions']
export type SectionName = NonNullable<CvRenderOptions['hidden_sections']>[number]
export type TemplateInfo = Schemas['TemplateInfo']
export type TemplateList = Schemas['TemplateList']
export type UploadInfo = Schemas['UploadInfo']
export type DefaultTemplateResult = Schemas['DefaultTemplateResult']
export type SourceView = Schemas['SourceView']
export type SourceInput = Schemas['SourceInput']
export type SourceTestResult = Schemas['SourceTestResult']
export type SourceRunResult = Schemas['SourceRunResult']
export type ConnectorKind = SourceInput['kind']
export type AgentBrowseSource = Schemas['AgentBrowseSource']
export type BrowseAccess = AgentBrowseSource['access']
export type AgentBrowseLimits = Schemas['AgentBrowseLimits']
export type LinkedInPublicView = Schemas['LinkedInPublicView']
export type LinkedInPublicRunResult = Schemas['LinkedInPublicRunResult']
export type PromptView = Schemas['PromptView']
export type AlertList = Schemas['AlertList']
export type AlertJob = Schemas['AlertJob']
export type EmailPollResult = Schemas['EmailPollResult']
export type Board = Schemas['Board']
export type BoardCard = Schemas['BoardCard']
export type BoardMove = Schemas['BoardMove']
export type EventType = Schemas['EventType']
export type ProcessView = Schemas['ProcessView']
export type ReceivedOffer = Schemas['ReceivedOfferOut']
export type ReceivedOfferFields = Schemas['ReceivedOfferFields']
export type OfferComparison = Schemas['OfferComparison']
export type JobPackage = Schemas['JobPackage']
export type JobCoverLetter = Schemas['JobCoverLetter']
export type CoverLetterView = Schemas['CoverLetterView']
export type LetterRenderResult = Schemas['LetterRenderResult']
export type LetterTemplateInfo = Schemas['LetterTemplateInfo']
export type MilestoneOut = Schemas['MilestoneOut']
export type MilestoneKind = Schemas['MilestoneCreate']['kind']
export type InterviewType = NonNullable<Schemas['MilestoneOut']['interview_type']>
export type ContactOut = Schemas['ContactOut']
export type UpcomingItem = Schemas['UpcomingItem']
export type CalendarItem = Schemas['CalendarItem']
export type FollowupList = Schemas['FollowupList']
export type FunnelStats = Schemas['FunnelStats']
export type Calibration = Schemas['Calibration']
export type CalibrationGroup = Schemas['CalibrationGroup']
export type SearchStory = Schemas['SearchStory']
export type ApplicationChannel = NonNullable<Schemas['AddUserEventBody']['channel']>
export type AssistedApplication = Schemas['AssistedApplication']
export type AttemptView = Schemas['AttemptView']
export type FieldReport = Schemas['FieldReport']
export type ContextStatus = Schemas['ContextStatus']
export type ContextFileInfo = Schemas['ContextFileInfo']
export type AgentRunView = Schemas['AgentRunView']
export type AgentEntry = Schemas['AgentEntry']
export type AgentsOverview = Schemas['AgentsOverview']
export type AgentPreferences = Schemas['Preferences']
export type AgentResolution = Schemas['Resolution']
export type LocalModelsStatus = Schemas['LocalModelsStatus']
export type SpendTiers = Schemas['TiersView']
export type SpendTier = Schemas['TierView']
export type AgentRunList = Schemas['AgentRunList']
export type AgentCosts = Schemas['AgentCosts']
export type CostWindow = Schemas['CostWindow']
export type CostGroup = Schemas['CostGroup']
export type CostTotals = Schemas['CostTotals']
export type AssessThreshold = Schemas['AssessThreshold']
export type JobCost = Schemas['JobCost']
export type AgentRequestView = Schemas['AgentRequestView']
export type AgentRequestList = Schemas['AgentRequestList']
export type OpenFolderResult = Schemas['OpenFolderResult']
export type ReplyInboxItem = Schemas['ReplyInboxItem']
export type ReplyView = Schemas['ReplyView']
export type ReplyProposal = Schemas['ReplyProposal']
export type RepliesPollResult = Schemas['RepliesPollResult']
export type MessageDraftOut = Schemas['MessageDraftOut']
export type JobNetwork = Schemas['JobNetwork']
export type NetworkPerson = Schemas['NetworkPerson']
export type NetworkStatus = Schemas['NetworkStatus']
export type CompanyResearchResult = Schemas['CompanyResearchResult']
export type CompanyResearchContent = Schemas['CompanyResearchContent']
export type ContactRelation = NonNullable<Schemas['ContactOut']['relation']>
export type ReferralStatus = NonNullable<Schemas['ContactOut']['referral']>

// En desarrollo (`pnpm dev`, 5173) la API está en 8000; la UI compilada la sirve la propia API
// (`cai start`, fase 23.4), así que llama a su mismo origen, sea cual sea el puerto.
export const API_URL: string =
  import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://127.0.0.1:8000' : window.location.origin)

/** Ficheros que sirve la API (PDF y DOCX de un render, preview de una plantilla). */
export const fileUrls = {
  renderPdf: (renderId: number) => `${API_URL}/renders/${renderId}/pdf`,
  renderDocx: (renderId: number) => `${API_URL}/renders/${renderId}/docx`,
  /** La carta en TXT (UTF-8, saltos de Windows) para descargar. */
  letterText: (documentId: number) => `${API_URL}/cover-letters/${documentId}/text`,
  templatePreview: (templateId: string) =>
    `${API_URL}/templates/${encodeURIComponent(templateId)}/preview.png`,
  /** Primera página del CV original del que se creó la plantilla. */
  templateSource: (templateId: string) =>
    `${API_URL}/templates/${encodeURIComponent(templateId)}/source.png`,
  /** La plantilla con tu perfil real; la primera vez tarda lo que la conversión a PDF. */
  templateRealPreview: (templateId: string, version: string | number = '') =>
    `${API_URL}/templates/${encodeURIComponent(templateId)}/preview-real.png${version ? `?v=${version}` : ''}`,
  /** Un hito como `.ics` para importarlo en el calendario. */
  milestoneIcs: (milestoneId: number) => `${API_URL}/milestones/${milestoneId}/ics`,
  /** La guía de preparación de una entrevista en PDF. */
  interviewGuide: (milestoneId: number) => `${API_URL}/milestones/${milestoneId}/guide.pdf`,
  interviewGuideCover: (milestoneId: number) => `${API_URL}/milestones/${milestoneId}/guide.png`,
  /** Feed con todos los hitos futuros (para suscribirse) y su versión para descargar. */
  calendarFeed: `${API_URL}/calendar.ics`,
  calendarDownload: `${API_URL}/calendar.ics?download=true`,
  /** Captura de un intento de candidatura asistida; `version` evita la caché al cambiar. */
  applicationScreenshot: (attemptId: number, kind: 'review' | 'confirmation', version: string) =>
    `${API_URL}/apply/${attemptId}/screenshot/${kind}?v=${encodeURIComponent(version)}`,
}

export const api = createClient<paths>({
  baseUrl: API_URL,
  // Se resuelve en cada llamada (no al crear el cliente) para que los tests puedan simularlo.
  fetch: (request) => globalThis.fetch(request),
})

/** Error de la API con el formato común `{ok: false, error: {type, message, details}}`. */
export class ApiError extends Error {
  readonly type: string
  readonly status: number
  readonly details: ErrorDetail[]

  constructor(message: string, type: string, status: number, details: ErrorDetail[] = []) {
    super(message)
    this.name = 'ApiError'
    this.type = type
    this.status = status
    this.details = details
  }
}

/** La API no responde: el mensaje, en el idioma activo al lanzarlo. */
const offline = () => new ApiError(i18n.t('errors.offline'), 'offline', 0)

interface Result<T> {
  data?: T
  error?: unknown
  response: Response
}

function isErrorBody(value: unknown): value is Schemas['ErrorResponse'] {
  return typeof value === 'object' && value !== null && 'error' in value
}

/** Devuelve `data` o lanza `ApiError`. Envuelve la llamada para detectar la API caída. */
export async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  let result: Result<T>
  try {
    result = await call
  } catch {
    throw offline()
  }
  const { data, error, response } = result
  if (error !== undefined || data === undefined) {
    if (isErrorBody(error)) {
      const { message, type, details } = error.error
      throw new ApiError(message, type, response.status, details ?? [])
    }
    throw new ApiError(i18n.t('errors.unexpected', { status: response.status }), 'unknown', response.status)
  }
  return data
}
