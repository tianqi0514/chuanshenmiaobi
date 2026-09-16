import { useEffect, useMemo, useState } from 'react';
import {
  Check, Clipboard, Clock3, Code2, FileText, FolderPlus, HelpCircle, LoaderCircle, Upload, X,
} from 'lucide-react';

type Item = Record<string, unknown> & { id: string };
type Step = {
  key: string; title: string; short_title: string; input_label: string; output_label: string;
  purpose: string; principle: string; writing_value: string; guardrail: string; prompt: string;
  execution_mode: 'manual' | 'deterministic' | 'model' | 'hybrid'; requires_model: boolean;
  items: Item[]; count: number; status: string; elapsed_ms?: number;
};
type Preview = { document: Item; steps: Step[]; summary: Record<string, number>; model?: { name: string; provider: string } };
type ModelStatus = { configured: boolean; provider: string | null; model: string | null; enable_thinking: boolean };
type Project = { id: string; name: string; created_at: string; updated_at: string };
type ExtractionRun = {
  id: string; project_id: string; filename: string; material_role: string; status: 'running' | 'completed' | 'failed';
  model_name: string | null; summary: Record<string, number>; error: string | null; created_at: string;
  completed_at: string | null; result?: Preview | null;
};

const roles = [
  ['task_data', '本次业务资料'], ['policy_basis', '政策与制度依据'], ['reference', '参考材料'],
  ['sample_style', '样稿与格式'], ['attachment', '报告附件'],
];

const modeLabels: Record<Step['execution_mode'], string> = {
  manual: '用户确认', deterministic: '确定性处理', model: '大模型抽取', hybrid: '模型 + 程序校验',
};

function itemTitle(step: Step, item: Item): string {
  if (step.key === 'material_role') return String(item.filename || item.id);
  if (step.key === 'evidence') return String(item.text || item.id);
  if (step.key === 'entity' || step.key === 'metric') return String(item.name || item.id);
  if (step.key === 'claim') return `${String(item.subject)} ${String(item.predicate)} ${String(item.object_text)}`;
  if (step.key === 'fact') return `${String(item.subject)} ${String(item.predicate)} ${String(item.object_value)}`;
  if (step.key === 'relation') return `${String(item.subject_entity_id)} —${String(item.predicate)}→ ${String(item.object_entity_id)}`;
  if (step.key === 'sample_profile') return String(item.document_type || item.id);
  return String(item.title || item.name || item.id);
}

function statusText(step: Step): string {
  if (step.status === 'completed') return `${step.count} 项结果`;
  if (step.status === 'not_required') return '本次跳过';
  return '尚未运行';
}

function runStatusText(run: ExtractionRun): string {
  if (run.status === 'completed') return '已完成';
  if (run.status === 'failed') return '失败';
  return '处理中';
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value));
}

export function App() {
  const [steps, setSteps] = useState<Step[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [model, setModel] = useState<ModelStatus | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState('');
  const [newProjectName, setNewProjectName] = useState('');
  const [creatingProject, setCreatingProject] = useState(false);
  const [runs, setRuns] = useState<ExtractionRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState('');
  const [loadingRun, setLoadingRun] = useState(false);
  const [selectedKey, setSelectedKey] = useState('material_role');
  const [helpKey, setHelpKey] = useState<string | null>(null);
  const [view, setView] = useState<'input' | 'prompt' | 'result'>('result');
  const [file, setFile] = useState<File | null>(null);
  const [role, setRole] = useState('task_data');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const activeSteps = preview?.steps || steps;
  const selectedIndex = Math.max(0, activeSteps.findIndex((step) => step.key === selectedKey));
  const selected = activeSteps[selectedIndex];
  const helpStep = activeSteps.find((step) => step.key === helpKey);
  const input = useMemo(
    () => selectedIndex > 0 ? (activeSteps[selectedIndex - 1]?.items || []) : (selected?.items || []),
    [activeSteps, selected, selectedIndex],
  );

  useEffect(() => {
    Promise.all([
      fetch('/api/v1/extraction/steps').then((response) => response.json()),
      fetch('/api/v1/models/status').then((response) => response.json()),
      fetch('/api/v1/projects').then((response) => response.json()),
    ]).then(([rows, modelStatus, projectRows]: [Step[], ModelStatus, Project[]]) => {
      setSteps(rows.map((row: Step) => ({ ...row, items: [], count: 0, status: 'not_run', elapsed_ms: 0 })));
      setModel(modelStatus);
      setProjects(projectRows);
      const remembered = window.localStorage.getItem('miaobi.project_id');
      const initialProject = projectRows.find((project) => project.id === remembered) || projectRows[0];
      setProjectId(initialProject?.id || '');
    }).catch(() => setError('初始化失败，请检查 API 服务'));
  }, []);

  useEffect(() => {
    if (!projectId) {
      setRuns([]); setPreview(null); setSelectedRunId('');
      return;
    }
    window.localStorage.setItem('miaobi.project_id', projectId);
    const controller = new AbortController();
    const restore = async () => {
      setLoadingRun(true); setError('');
      try {
        const response = await fetch(`/api/v1/projects/${projectId}/runs`, { signal: controller.signal });
        if (!response.ok) throw new Error('加载抽取记录失败');
        const rows: ExtractionRun[] = await response.json();
        setRuns(rows);
        const latest = rows.find((run) => run.status === 'completed');
        if (!latest) {
          setPreview(null); setSelectedRunId(''); setSelectedKey('material_role');
          return;
        }
        const detailResponse = await fetch(`/api/v1/projects/${projectId}/runs/${latest.id}`, { signal: controller.signal });
        if (!detailResponse.ok) throw new Error('恢复抽取结果失败');
        const detail: ExtractionRun = await detailResponse.json();
        setPreview(detail.result || null); setSelectedRunId(detail.id); setSelectedKey('evidence'); setView('result');
      } catch (reason) {
        if (!(reason instanceof DOMException && reason.name === 'AbortError')) {
          setError(reason instanceof Error ? reason.message : '加载抽取记录失败');
        }
      } finally { if (!controller.signal.aborted) setLoadingRun(false); }
    };
    void restore();
    return () => controller.abort();
  }, [projectId]);

  const createProject = async () => {
    const name = newProjectName.trim();
    if (!name) return;
    setCreatingProject(true); setError('');
    try {
      const response = await fetch('/api/v1/projects', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || '项目创建失败');
      setProjects((current) => [body, ...current]); setProjectId(body.id); setNewProjectName('');
    } catch (reason) { setError(reason instanceof Error ? reason.message : '项目创建失败'); }
    finally { setCreatingProject(false); }
  };

  const loadRun = async (runId: string) => {
    if (!projectId || runId === selectedRunId) return;
    setLoadingRun(true); setError('');
    try {
      const response = await fetch(`/api/v1/projects/${projectId}/runs/${runId}`);
      const body: ExtractionRun & { detail?: string } = await response.json();
      if (!response.ok) throw new Error(body.detail || '读取抽取结果失败');
      if (!body.result) throw new Error(body.error || '本次抽取没有可展示的结果');
      setPreview(body.result); setSelectedRunId(body.id); setSelectedKey('evidence'); setView('result');
    } catch (reason) { setError(reason instanceof Error ? reason.message : '读取抽取结果失败'); }
    finally { setLoadingRun(false); }
  };

  const run = async () => {
    if (!file || !projectId) return;
    setLoading(true); setError('');
    const form = new FormData(); form.set('file', file); form.set('material_role', role);
    try {
      const response = await fetch(`/api/v1/projects/${projectId}/extractions/run`, { method: 'POST', body: form });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || '抽取失败');
      setPreview(body.result); setSelectedRunId(body.id); setSelectedKey('evidence'); setView('result');
      const runsResponse = await fetch(`/api/v1/projects/${projectId}/runs`);
      if (runsResponse.ok) setRuns(await runsResponse.json());
    } catch (reason) { setError(reason instanceof Error ? reason.message : '抽取失败'); }
    finally {
      setLoading(false);
      const runsResponse = await fetch(`/api/v1/projects/${projectId}/runs`);
      if (runsResponse.ok) setRuns(await runsResponse.json());
    }
  };

  const copyPrompt = async () => {
    if (!selected) return;
    await navigator.clipboard.writeText(selected.prompt);
    setCopied(true); window.setTimeout(() => setCopied(false), 1200);
  };

  return <div className="app">
    <header>
      <div className="brand"><div className="mark">妙</div><div><b>传神妙笔</b><small>五层抽取验证</small></div></div>
      <div className={`model-pill ${model?.configured ? 'ready' : ''}`}>
        <span />{model?.configured ? `${model.model} · 已配置` : '大模型未配置'}
      </div>
    </header>
    <main>
      <section className="project-bar">
        <div className="project-field">
          <small>当前项目</small>
          <select aria-label="当前项目" value={projectId} onChange={(event) => { setProjectId(event.target.value); setFile(null); }}>
            {!projects.length && <option value="">请先新建项目</option>}
            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
        </div>
        <div className="project-create">
          <input aria-label="新项目名称" value={newProjectName} maxLength={120} placeholder="新项目名称" onChange={(event) => setNewProjectName(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void createProject(); }} />
          <button type="button" disabled={!newProjectName.trim() || creatingProject} onClick={() => void createProject()}>{creatingProject ? <LoaderCircle className="spin" size={16} /> : <FolderPlus size={16} />}新建</button>
        </div>
      </section>
      <section className="upload-card">
        <label className="file-picker"><FileText size={20} /><span>{file ? file.name : '选择一份材料'}</span><input type="file" accept=".pdf,.docx,.xlsx,.csv,.txt,.md,.rst,.html,.json,.yaml,.yml,.xml" onChange={(event) => setFile(event.target.files?.[0] || null)} /></label>
        <select aria-label="材料用途" value={role} onChange={(event) => setRole(event.target.value)}>{roles.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <button className="primary" type="button" disabled={!file || !projectId || loading || model?.configured === false} onClick={() => void run()}>{loading ? <><LoaderCircle className="spin" size={17} />抽取中</> : <><Upload size={17} />开始抽取</>}</button>
      </section>
      {loading && <div className="running">正在依次执行解析、Evidence、Entity、Claim、Fact、Relation 和指标识别，请勿重复提交。</div>}
      {error && <div className="error">{error}</div>}
      <section className="run-history">
        <div className="run-history-head"><div><Clock3 size={16} /><b>抽取记录</b></div>{loadingRun && <LoaderCircle className="spin" size={15} />}</div>
        {!projectId ? <div className="run-empty">新建项目后，抽取记录会保存在该项目中。</div> : !runs.length ? <div className="run-empty">当前项目暂无抽取记录。</div> : <div className="run-list">{runs.map((runItem) => <button type="button" key={runItem.id} className={`run-item ${selectedRunId === runItem.id ? 'active' : ''} ${runItem.status}`} disabled={runItem.status !== 'completed'} onClick={() => void loadRun(runItem.id)}>
          <span className="run-dot" /><span className="run-name">{runItem.filename}</span><small>{formatTime(runItem.created_at)} · {runStatusText(runItem)}</small>
        </button>)}</div>}
      </section>
      <section className="workspace">
        <nav>{activeSteps.map((step, index) => <div className={`step-row ${step.key === selected?.key ? 'active' : ''}`} key={step.key}>
          <button type="button" className="step-main" onClick={() => setSelectedKey(step.key)}>
            <span>{index + 1}</span><div><b>{step.title}</b><small>{statusText(step)}</small></div>
          </button>
          <button type="button" className="step-help" aria-label={`查看${step.title}原理`} title="查看这一步的原理" onClick={() => setHelpKey(step.key)}><HelpCircle size={15} /></button>
        </div>)}</nav>
        <article className="panel">
          {selected ? <>
            <div className="panel-head"><div><small>第 {selectedIndex + 1} 步 · {modeLabels[selected.execution_mode]}</small><h1>{selected.title}</h1></div><div className="head-status"><span className={selected.status === 'completed' ? 'status done' : 'status'}>{selected.status === 'completed' ? '已完成' : selected.status === 'not_required' ? '本次不需要' : '尚未运行'}</span>{Boolean(selected.elapsed_ms) && <small>{selected.elapsed_ms} ms</small>}</div></div>
            <div className="tabs"><button className={view === 'input' ? 'active' : ''} onClick={() => setView('input')}>输入</button><button className={view === 'prompt' ? 'active' : ''} onClick={() => setView('prompt')}>提示词</button><button className={view === 'result' ? 'active' : ''} onClick={() => setView('result')}>结果</button>{view === 'prompt' && <button className="copy" onClick={() => void copyPrompt()}>{copied ? <Check size={14} /> : <Clipboard size={14} />}{copied ? '已复制' : '复制'}</button>}</div>
            <div className="content">
              {view === 'prompt' && <pre className="prompt">{selected.prompt}</pre>}
              {view === 'input' && <pre className="json"><Code2 size={15} />{JSON.stringify(input, null, 2)}</pre>}
              {view === 'result' && (!selected.items?.length ? <div className="empty">{selected.status === 'not_required' ? '当前材料不需要执行此步骤。' : '该步骤尚未执行，不展示模拟结果。'}</div> : <div className="results">{selected.items.map((item) => <details key={item.id}><summary><b>{itemTitle(selected, item)}</b>{selected.key === 'evidence' && <small>{[item.page ? `第 ${item.page} 页` : '', item.path].filter(Boolean).join(' · ')}</small>}{selected.key === 'material_role' && <small>{String(item.parser)} · {String(item.element_count)} 个结构元素</small>}</summary><pre>{JSON.stringify(item, null, 2)}</pre></details>)}</div>)}
            </div>
          </> : <div className="empty"><LoaderCircle className="spin" />正在加载</div>}
        </article>
      </section>
    </main>
    {helpStep && <div className="modal-backdrop" role="presentation" onMouseDown={() => setHelpKey(null)}>
      <section className="help-dialog" role="dialog" aria-modal="true" aria-label={`${helpStep.title}原理`} onMouseDown={(event) => event.stopPropagation()}>
        <button className="dialog-close" aria-label="关闭" onClick={() => setHelpKey(null)}><X size={18} /></button>
        <small>{modeLabels[helpStep.execution_mode]}</small><h2>{helpStep.title}</h2>
        <dl><div><dt>这一步做什么</dt><dd>{helpStep.purpose}</dd></div><div><dt>原理</dt><dd>{helpStep.principle}</dd></div><div><dt>对后续写作的价值</dt><dd>{helpStep.writing_value}</dd></div><div><dt>边界</dt><dd>{helpStep.guardrail}</dd></div></dl>
      </section>
    </div>}
  </div>;
}
