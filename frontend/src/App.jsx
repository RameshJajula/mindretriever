import { useEffect, useState } from 'react'

export default function App() {
  const [targetPath, setTargetPath] = useState('.')
  const [fullRun, setFullRun] = useState(false)
  const [running, setRunning] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [status, setStatus] = useState('idle')
  const [result, setResult] = useState(null)
  const [runs, setRuns] = useState([])
  const [selectedFiles, setSelectedFiles] = useState([])

  async function refreshRuns() {
    const res = await fetch('/api/runs')
    if (!res.ok) return
    const data = await res.json()
    setRuns(data)
  }

  useEffect(() => {
    refreshRuns()
  }, [])

  async function onRun(e) {
    e.preventDefault()
    setRunning(true)
    setStatus('Running pipeline...')

    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: targetPath, full: fullRun }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Run failed')
      }
      const data = await res.json()
      setResult(data)
      setStatus('Run completed successfully')
      refreshRuns()
    } catch (err) {
      setStatus(`Run failed: ${err.message}`)
    } finally {
      setRunning(false)
    }
  }

  async function onUpload(e) {
    e.preventDefault()
    if (selectedFiles.length === 0) {
      setStatus('Select at least one .md, .docx, or .sql file')
      return
    }

    setUploading(true)
    setStatus('Uploading files...')

    const form = new FormData()
    selectedFiles.forEach((f) => form.append('files', f))

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: form,
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Upload failed')
      }
      const data = await res.json()
      setStatus(`Uploaded ${data.files_saved.length} files to ${data.folder}`)
    } catch (err) {
      setStatus(`Upload failed: ${err.message}`)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="page">
      <header className="hero">
        <h1>GraphMind Console</h1>
        <p>Python backend + React frontend + SQL run history + md/docx/sql ingestion.</p>
      </header>

      <section className="grid">
        <article className="card">
          <h2>Run Pipeline</h2>
          <form onSubmit={onRun}>
            <label>Target path</label>
            <input value={targetPath} onChange={(e) => setTargetPath(e.target.value)} placeholder="." />

            <label className="check">
              <input type="checkbox" checked={fullRun} onChange={(e) => setFullRun(e.target.checked)} />
              Force full run
            </label>

            <button disabled={running}>{running ? 'Running...' : 'Run GraphMind'}</button>
          </form>
          <p className="status">{status}</p>

          {result && (
            <div className="result">
              <p>Run ID: {result.run_id}</p>
              <p>Files: {result.files}</p>
              <p>Words: {result.words}</p>
              <p>Nodes: {result.nodes}</p>
              <p>Edges: {result.edges}</p>
              <p>Communities: {result.communities}</p>
              <p>Out Dir: {result.out_dir}</p>
            </div>
          )}
        </article>

        <article className="card">
          <h2>Upload Ingestion</h2>
          <form onSubmit={onUpload}>
            <input
              type="file"
              multiple
              accept=".md,.docx,.sql"
              onChange={(e) => setSelectedFiles(Array.from(e.target.files || []))}
            />
            <button disabled={uploading}>{uploading ? 'Uploading...' : 'Upload Files'}</button>
          </form>
          <small>Supported types: .md, .docx, .sql</small>
        </article>

        <article className="card">
          <h2>Recent Runs (SQL)</h2>
          <button onClick={refreshRuns}>Refresh</button>
          <ul className="runs">
            {runs.map((run) => (
              <li key={run.id}>
                <strong>#{run.id}</strong> {run.target_path}
                <span>{run.nodes} nodes / {run.edges} edges / {run.communities} communities</span>
                <span>{run.created_at}</span>
              </li>
            ))}
          </ul>
        </article>
      </section>
    </div>
  )
}
