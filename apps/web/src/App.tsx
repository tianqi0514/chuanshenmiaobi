import { useEffect, useMemo, useState } from 'react';
import { Check, ChevronRight, Clipboard, Code2, FileText, LoaderCircle, RefreshCw, Upload } from 'lucide-react';

type Item = Record<string, unknown> & { id: string };
type Step = {
  key: string; title: string; short_title: string; input_label: string; output_label: string;
  purpose: string; prompt: string; items: Item[]; count: number; status: string;
};
type Preview = { document: Item; steps: Step[]; summary: { elements: number; evidence: number } };

const roles = [
  ['task_data', '本次业务资料'], ['policy_basis', '政策与制度依据'], ['reference', '参考材料'],
  ['sample_style', '样稿与格式'], ['attachment', '报告附件'],
];

function itemTitle(step: Step, item: Item): string {
  if (step.key === 'material_role') return String(item.filename || item.id);
  if (step.key === 'evidence') return String(item.text || item.id);
  return String(item.title || item.name || item.id);
}

export function App() {
  const [steps, setSteps] = useState<Step[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [selectedKey, setSelectedKey] = useState('material_role');
  const [view, setView] = useState<'input' | 'prompt' | 'result'>('result');
  const [file, setFile] = useState<File | null>(null);
  const [role, setRole] = useState('task_data');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const activeSteps = preview?.steps || steps;
  const selectedIndex = Math.max(0, activeSteps.findIndex((step) => step.key === selectedKey));
  const selected = activeSteps[selectedIndex];
  const input = useMemo(() => selectedIndex > 0 ? (activeSteps[selectedIndex - 1]?.items || []) : (selected?.items || []), [activeSteps, selected, selectedIndex]);

  useEffect(() => {
    fetch('/api/v1/extraction/steps').then((response) => response.json()).then((rows) => {
      setSteps(rows.map((row: Step) => ({ ...row, items: [], count: 0, status: 'not_run' })));
    }).catch(() => setError('抽取步骤加载失败'));
  }, []);

  const run = async () => {
    if (!file) return;
    setLoading(true); setError('');
    const form = new FormData(); form.set('file', file); form.set('material_role', role);
    try {
      const response = await fetch('/api/v1/extraction/preview', { method: 'POST', body: form });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || '文件解析失败');
      setPreview(body); setSelectedKey('evidence'); setView('result');
    } catch (reason) { setError(reason instanceof Error ? reason.message : '文件解析失败'); }
    finally { setLoading(false); }
  };

  const copyPrompt = async () => {
    if (!selected) return;
    await navigator.clipboard.writeText(selected.prompt);
    setCopied(true); window.setTimeout(() => setCopied(false), 1200);
  };

  return <div className="app">
    <header><div className="mark">妙</div><div><b>传神妙笔</b><small>材料抽取验证</small></div></header>
    <main>
      <section className="upload-card">
        <label className="file-picker"><FileText size={20} /><span>{file ? file.name : '选择一份材料'}</span><input type="file" accept=".pdf,.docx,.xlsx,.csv,.txt,.md,.rst,.html,.json,.yaml,.yml,.xml" onChange={(event) => setFile(event.target.files?.[0] || null)} /></label>
        <select aria-label="材料用途" value={role} onChange={(event) => setRole(event.target.value)}>{roles.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <button className="primary" type="button" disabled={!file || loading} onClick={() => void run()}>{loading ? <><LoaderCircle className="spin" size={17} />解析中</> : <><Upload size={17} />开始解析</>}</button>
      </section>
      {error && <div className="error">{error}</div>}
      <section className="workspace">
        <nav>{activeSteps.map((step, index) => <button type="button" key={step.key} className={step.key === selected?.key ? 'active' : ''} onClick={() => setSelectedKey(step.key)}>
          <span>{index + 1}</span><div><b>{step.title}</b><small>{step.status === 'completed' ? `${step.count} 项结果` : step.status === 'not_required' ? '本次跳过' : '尚未运行'}</small></div><ChevronRight size={15} />
        </button>)}</nav>
        <article className="panel">
          {selected ? <>
            <div className="panel-head"><div><small>第 {selectedIndex + 1} 步</small><h1>{selected.title}</h1></div><span className={selected.status === 'completed' ? 'status done' : 'status'}>{selected.status === 'completed' ? '已完成' : selected.status === 'not_required' ? '本次不需要' : '尚未运行'}</span></div>
            <div className="tabs"><button className={view === 'input' ? 'active' : ''} onClick={() => setView('input')}>输入</button><button className={view === 'prompt' ? 'active' : ''} onClick={() => setView('prompt')}>提示词</button><button className={view === 'result' ? 'active' : ''} onClick={() => setView('result')}>结果</button>{view === 'prompt' && <button className="copy" onClick={() => void copyPrompt()}>{copied ? <Check size={14} /> : <Clipboard size={14} />}{copied ? '已复制' : '复制'}</button>}</div>
            <div className="content">
              {view === 'prompt' && <pre className="prompt">{selected.prompt}</pre>}
              {view === 'input' && <pre className="json"><Code2 size={15} />{JSON.stringify(input, null, 2)}</pre>}
              {view === 'result' && (!selected.items?.length ? <div className="empty">{selected.status === 'not_required' ? '当前材料不需要执行此步骤。' : '该步骤尚未执行，不展示模拟结果。'}</div> : <div className="results">{selected.items.map((item) => <div key={item.id}><b>{itemTitle(selected, item)}</b>{selected.key === 'evidence' && <small>{[item.page ? `第 ${item.page} 页` : '', item.path].filter(Boolean).join(' · ')}</small>}{selected.key === 'material_role' && <small>{String(item.parser)} · {String(item.element_count)} 个结构元素</small>}</div>)}</div>)}
            </div>
          </> : <div className="empty"><RefreshCw className="spin" />正在加载</div>}
        </article>
      </section>
    </main>
  </div>;
}

