import { useState } from 'react'
import { useIssueRunnerKey } from '@/lib/api/hooks/agents'
import type { ApiKeyCreated } from '@/lib/api/types'
import { describeError } from '@/lib/api/errors'
import { Button } from '@/components/ui/Button'
import { KeyRevealDialog } from '@/features/keys/ApiKeys'

/**
 * Admin → Bots: the claude-trader's runner key. With it the trader finds your bots that have a strategy saved on
 * their page and gets their keys itself, so a new bot starts with no file to edit on the server.
 */
export function RunnerKeyCard() {
  const issue = useIssueRunnerKey()
  const [created, setCreated] = useState<ApiKeyCreated | null>(null)
  const error = issue.error ? describeError(issue.error) : null
  return (
    <section aria-label="Claude trader runner key" className="rounded-lg border border-divider bg-bg-1 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1 basis-64">
          <h2 className="text-section font-semibold">Claude trader runner key</h2>
          <p className="text-caption text-text-2">
            Put it in the trader&apos;s agents.toml once, as <code>[runner] key</code>. The trader then runs every bot of yours that has a strategy saved on its page and gets its key by itself. A new key ends the old one.
          </p>
        </div>
        <Button variant="secondary" size="sm" disabled={issue.isPending} onClick={() => issue.mutate(undefined, { onSuccess: (k) => setCreated(k) })}>
          {issue.isPending ? 'Issuing…' : 'Issue runner key'}
        </Button>
      </div>
      {error ? (
        <p role="alert" className="mt-2 text-caption text-down">
          {error.title}
          {error.detail ? <span className="block text-text-2">{error.detail}</span> : null}
        </p>
      ) : null}
      <KeyRevealDialog created={created} onClose={() => setCreated(null)} />
    </section>
  )
}
