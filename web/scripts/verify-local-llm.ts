import { existsSync } from 'node:fs'
import path from 'node:path'

type BunRuntime = typeof globalThis & {
  Bun: {
    sleep: (ms: number) => Promise<void>
    spawn: (options: {
      cmd: string[]
      cwd: string
      env: Record<string, string | undefined>
      stdout: 'ignore'
      stderr: 'pipe'
    }) => {
      kill: () => void
      exited: Promise<number>
      exitCode: number | null
      stderr: ReadableStream<Uint8Array> | null
    }
    spawnSync: (options: {
      cmd: string[]
      cwd: string
      stderr: 'pipe'
      stdout: 'ignore'
    }) => {
      exitCode: number
      stderr: { toString: () => string }
    }
  }
}

const bunRuntime = globalThis as BunRuntime

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) {
    throw new Error(message)
  }
}

async function waitForHealthy(baseUrl: string, timeoutMs: number) {
  const deadline = Date.now() + timeoutMs
  let lastError = 'backend did not start'

  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseUrl}/llm/health`)
      if (response.ok) {
        return
      }
      lastError = `health returned ${response.status}`
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error)
    }

    await bunRuntime.Bun.sleep(250)
  }

  throw new Error(`Timed out waiting for mounted LLM endpoint: ${lastError}`)
}

async function main() {
  const projectRoot = process.cwd() // web/
  const serverRoot = path.resolve(projectRoot, '..', 'server')
  const venvPython = path.join(serverRoot, 'venv', 'bin', 'python')

  if (!existsSync(venvPython)) {
    throw new Error('Missing server/venv/bin/python. Run bun run setup before verify:local:llm.')
  }

  const dependencyCheck = bunRuntime.Bun.spawnSync({
    cmd: [venvPython, '-c', 'import dotenv, fastapi, uvicorn'],
    cwd: serverRoot,
    stderr: 'pipe',
    stdout: 'ignore',
  })
  if (dependencyCheck.exitCode !== 0) {
    const stderr = dependencyCheck.stderr.toString().trim()
    throw new Error(
      `The backend virtualenv is missing required packages. Run bun run setup before verify:local:llm.${stderr ? ` Python said: ${stderr}` : ''}`,
    )
  }

  const port = 43160 + Math.floor(Math.random() * 20)
  const baseUrl = `http://127.0.0.1:${port}`

  const serverProcess = bunRuntime.Bun.spawn({
    cmd: [venvPython, 'scripts/run_fake_server.py'],
    cwd: serverRoot,
    env: {
      ...process.env,
      AGORA_APP_ID: '0123456789abcdef0123456789abcdef',
      AGORA_APP_CERTIFICATE: 'fedcba9876543210fedcba9876543210',
      CUSTOM_LLM_URL: 'https://example.ngrok-free.dev/llm/chat/completions',
      CUSTOM_LLM_API_KEY: 'test-key',
      PORT: String(port),
    },
    stdout: 'ignore',
    stderr: 'pipe',
  })

  try {
    await waitForHealthy(baseUrl, 10_000)

    const response = await fetch(`${baseUrl}/llm/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer any-key-here',
      },
      body: JSON.stringify({
        model: 'mock-model',
        messages: [{ role: 'user', content: 'Hello' }],
        stream: true,
      }),
    })

    assert(response.status === 200, 'POST /llm/chat/completions should return 200 for a streaming request')
    assert(
      (response.headers.get('content-type') ?? '').includes('text/event-stream'),
      'POST /llm/chat/completions should return a text/event-stream response',
    )

    const body = await response.text()
    assert(
      body.includes('"role": "assistant"') || body.includes('"role":"assistant"'),
      'SSE stream should open with an assistant role delta',
    )
    assert(
      body.includes('"finish_reason": "stop"') || body.includes('"finish_reason":"stop"'),
      'SSE stream should close the choice with finish_reason "stop"',
    )
    assert(
      body.trimEnd().endsWith('data: [DONE]'),
      'SSE stream should terminate with data: [DONE]',
    )

    const nonStream = await fetch(`${baseUrl}/llm/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'mock-model',
        messages: [{ role: 'user', content: 'Hi' }],
        stream: false,
      }),
    })
    assert(nonStream.status === 400, 'Non-streaming requests should be rejected with 400')

    console.log('Mounted LLM endpoint contract check passed')
  } finally {
    serverProcess.kill()
    await serverProcess.exited

    if (serverProcess.exitCode && serverProcess.exitCode !== 0) {
      const stderr = await new Response(serverProcess.stderr).text()
      if (stderr.trim()) {
        console.error(stderr.trim())
      }
    }
  }
}

await main()
