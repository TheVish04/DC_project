import { useEffect, useMemo, useRef, useState } from 'react';

const defaultPeerUrl = import.meta.env.VITE_PEER_URL || 'http://127.0.0.1:9001';
const defaultTrackerUrl = import.meta.env.VITE_TRACKER_URL || 'http://127.0.0.1:8000';

function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** index;
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}

function firstOnlineReplica(file, currentPeerId) {
  const replicas = file.replicas || [];
  return (
    replicas.find((replica) => replica.status === 'online' && replica.peer_id !== currentPeerId)
    || replicas.find((replica) => replica.status === 'online')
    || replicas[0]
  );
}

function saveBlob(blob, filename) {
  const blobUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(blobUrl);
}

function replicaSummary(file) {
  if (!file.replicas?.length) return 'No replicas registered';
  return file.replicas
    .map((replica) => `${replica.name} (${replica.status})`)
    .join(', ');
}

export default function App() {
  const [peerUrl, setPeerUrl] = useState(defaultPeerUrl);
  const [trackerUrl, setTrackerUrl] = useState(defaultTrackerUrl);
  const [peerInfo, setPeerInfo] = useState(null);
  const [peers, setPeers] = useState([]);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [subject, setSubject] = useState('');
  const [semester, setSemester] = useState('');
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState('Start the tracker and one peer, then refresh status.');
  const [busy, setBusy] = useState(false);
  const fileInputRef = useRef(null);

  const onlinePeers = useMemo(
    () => peers.filter((peer) => peer.status === 'online').length,
    [peers],
  );

  async function loadStatus() {
    try {
      const [peerResponse, peersResponse] = await Promise.all([
        fetch(`${peerUrl}/info`),
        fetch(`${trackerUrl}/peers`),
      ]);
      if (!peerResponse.ok) throw new Error('Peer is not reachable');
      if (!peersResponse.ok) throw new Error('Tracker is not reachable');
      setPeerInfo(await peerResponse.json());
      const peerData = await peersResponse.json();
      setPeers(peerData.peers || []);
      setMessage('Status refreshed.');
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function uploadNote(event) {
    event.preventDefault();
    if (!file) {
      setMessage('Choose a note file first.');
      return;
    }
    const formData = new FormData();
    formData.append('file', file);
    formData.append('subject', subject);
    formData.append('semester', semester);

    setBusy(true);
    try {
      const response = await fetch(`${peerUrl}/upload-note`, {
        method: 'POST',
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Upload failed');
      setMessage(`Uploaded ${payload.file.filename} and announced it to the tracker.`);
      setSubject('');
      setSemester('');
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      await loadStatus();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function searchNotes(event) {
    event?.preventDefault();
    setBusy(true);
    try {
      const response = await fetch(`${peerUrl}/search?q=${encodeURIComponent(query)}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Search failed');
      setResults(payload.results || []);
      setMessage(`Found ${payload.results?.length || 0} matching notes.`);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function downloadFile(fileRecord, replica) {
    setBusy(true);
    try {
      const currentPeerAlreadyHasFile = fileRecord.replicas?.some(
        (item) => item.peer_id === peerInfo?.peer_id,
      );

      if (!currentPeerAlreadyHasFile) {
        const response = await fetch(`${peerUrl}/download-from-peer`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            file_hash: fileRecord.file_hash,
            filename: fileRecord.filename,
            subject: fileRecord.subject,
            semester: fileRecord.semester,
            source_peer_url: replica.base_url,
          }),
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Peer-to-peer download failed');
      }

      const browserResponse = await fetch(`${peerUrl}/download/${fileRecord.file_hash}`);
      if (!browserResponse.ok) {
        const payload = await browserResponse.json().catch(() => ({}));
        throw new Error(payload.detail || 'Browser download failed');
      }
      saveBlob(await browserResponse.blob(), fileRecord.filename);
      setMessage(`Saved ${fileRecord.filename}. Hash verified${currentPeerAlreadyHasFile ? '' : ` from ${replica.name}`}.`);
      await loadStatus();
      await searchNotes();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadStatus();
  }, []);

  return (
    <main className="app-shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">Distributed Computing Project</p>
          <h1>P2P Notes Sharing</h1>
          <p className="lede">Upload notes on one peer and download them directly from another peer.</p>
        </div>
        <div className="status-strip" aria-label="System status">
          <span>{onlinePeers} online peers</span>
          <span>{peerInfo?.local_file_count ?? 0} local files</span>
        </div>
      </section>

      <section className="connection-panel">
        <label>
          Current peer API
          <input value={peerUrl} onChange={(event) => setPeerUrl(event.target.value)} />
        </label>
        <label>
          Tracker API
          <input value={trackerUrl} onChange={(event) => setTrackerUrl(event.target.value)} />
        </label>
        <button type="button" onClick={loadStatus} disabled={busy}>
          Refresh Status
        </button>
      </section>

      <p className="message" role="status">{message}</p>

      <section className="workspace">
        <form className="panel" onSubmit={uploadNote}>
          <div className="panel-heading">
            <p className="eyebrow">Peer Upload</p>
            <h2>Share a note</h2>
          </div>
          <label>
            Subject
            <input value={subject} onChange={(event) => setSubject(event.target.value)} placeholder="Distributed Computing" />
          </label>
          <label>
            Semester
            <input value={semester} onChange={(event) => setSemester(event.target.value)} placeholder="Sem 6" />
          </label>
          <label>
            Note file
            <input ref={fileInputRef} type="file" onChange={(event) => setFile(event.target.files?.[0] || null)} />
          </label>
          <button type="submit" disabled={busy}>
            Upload and Announce
          </button>
        </form>

        <section className="panel">
          <div className="panel-heading">
            <p className="eyebrow">Tracker Search</p>
            <h2>Find notes</h2>
          </div>
          <form className="search-row" onSubmit={searchNotes}>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by filename, subject, semester" />
            <button type="submit" disabled={busy}>Search</button>
          </form>
          <div className="result-list">
            {results.map((result) => {
              const replica = firstOnlineReplica(result, peerInfo?.peer_id);
              return (
                <article className="result-card" key={result.file_hash}>
                  <div>
                    <h3>{result.filename}</h3>
                    <p>{result.subject || 'No subject'} · {result.semester || 'No semester'} · {formatBytes(result.size)}</p>
                    <small>{result.replicas?.length || 0} replica(s) registered</small>
                    <span className="replica-line">Stored on: {replicaSummary(result)}</span>
                  </div>
                  <button
                    type="button"
                    disabled={busy || !replica}
                    onClick={() => downloadFile(result, replica)}
                  >
                    Download
                  </button>
                </article>
              );
            })}
            {results.length === 0 && <p className="empty">No notes listed yet.</p>}
          </div>
        </section>
      </section>

      <section className="peer-list">
        <div className="panel-heading">
          <p className="eyebrow">Live Peers</p>
          <h2>Network</h2>
        </div>
        <div className="peer-grid">
          {peers.map((peer) => (
            <article className="peer-card" key={peer.peer_id}>
              <strong>{peer.name}</strong>
              <span>{peer.peer_id}</span>
              <span>{peer.base_url}</span>
              <mark className={peer.status === 'online' ? 'online' : 'offline'}>{peer.status}</mark>
            </article>
          ))}
          {peers.length === 0 && <p className="empty">No peers registered yet.</p>}
        </div>
      </section>
    </main>
  );
}
