// Claves tipadas (fase 23.6): una clave que no esté en los textos en español no compila.
// Una línea por fichero de `src/locales/es/`.
import 'i18next'
import type agent from '@/locales/es/agent.json'
import type agentButton from '@/locales/es/agentButton.json'
import type agents from '@/locales/es/agents.json'
import type alerts from '@/locales/es/alerts.json'
import type apply from '@/locales/es/apply.json'
import type common from '@/locales/es/common.json'
import type cv from '@/locales/es/cv.json'
import type drafts from '@/locales/es/drafts.json'
import type funnel from '@/locales/es/funnel.json'
import type home from '@/locales/es/home.json'
import type inbox from '@/locales/es/inbox.json'
import type job from '@/locales/es/job.json'
import type labels from '@/locales/es/labels.json'
import type letter from '@/locales/es/letter.json'
import type match from '@/locales/es/match.json'
import type move from '@/locales/es/move.json'
import type nav from '@/locales/es/nav.json'
import type network from '@/locales/es/network.json'
import type newJob from '@/locales/es/newJob.json'
import type offers from '@/locales/es/offers.json'
import type pkg from '@/locales/es/pkg.json'
import type platforms from '@/locales/es/platforms.json'
import type process from '@/locales/es/process.json'
import type processes from '@/locales/es/processes.json'
import type profile from '@/locales/es/profile.json'
import type profileEditor from '@/locales/es/profileEditor.json'
import type prompts from '@/locales/es/prompts.json'
import type replies from '@/locales/es/replies.json'
import type research from '@/locales/es/research.json'
import type signals from '@/locales/es/signals.json'
import type skills from '@/locales/es/skills.json'
import type sources from '@/locales/es/sources.json'
import type status from '@/locales/es/status.json'
import type templates from '@/locales/es/templates.json'
import type triage from '@/locales/es/triage.json'

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'common'
    resources: {
      agent: typeof agent
      agentButton: typeof agentButton
      agents: typeof agents
      alerts: typeof alerts
      apply: typeof apply
      common: typeof common
      cv: typeof cv
      drafts: typeof drafts
      funnel: typeof funnel
      home: typeof home
      inbox: typeof inbox
      job: typeof job
      labels: typeof labels
      letter: typeof letter
      match: typeof match
      move: typeof move
      nav: typeof nav
      network: typeof network
      newJob: typeof newJob
      offers: typeof offers
      pkg: typeof pkg
      platforms: typeof platforms
      process: typeof process
      processes: typeof processes
      profile: typeof profile
      profileEditor: typeof profileEditor
      prompts: typeof prompts
      replies: typeof replies
      research: typeof research
      signals: typeof signals
      skills: typeof skills
      sources: typeof sources
      status: typeof status
      templates: typeof templates
      triage: typeof triage
    }
  }
}
