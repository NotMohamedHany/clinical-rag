import type { SourceRef } from '../../types';
import { IconLink } from '../common/Icons';

export function SourcesPanel({ sources }: { sources: SourceRef[] }) {
  if (!sources || sources.length === 0) return null;
  return (
    <div className="sources-panel">
      <div className="sources-head">
        <IconLink size={13} />
        Sources ({sources.length})
      </div>
      <div className="sources-list">
        {sources.map((s, i) => (
          <a key={i} className="source-chip" href={s.url} target="_blank" rel="noreferrer">
            <span className="source-chip-index">{i + 1}</span>
            <span className="source-chip-title">{s.title}</span>
          </a>
        ))}
      </div>
    </div>
  );
}
