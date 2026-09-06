import { FormEvent, useState } from 'react'
import {
  ArrowUp,
  BookOpen,
  ChevronRight,
  CircleHelp,
  FileText,
  History,
  Leaf,
  Menu,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react'

type Source = {
  id: string
  title: string
  authority: string
  section: string | null
  page: number
  excerpt: string
}

type Message = {
  id: number
  role: 'user' | 'assistant'
  text: string
  sources?: Source[]
  answerType?: 'direct' | 'abstain' | 'hand_off'
}

const starterQuestions = [
  'Do I need FSSAI registration for my home food business?',
  'What must appear in the ingredient list?',
  'How should I show the expiry date on my label?',
]

const initialMessages: Message[] = [
  {
    id: 1,
    role: 'assistant',
    text: 'Welcome to Shuruwat. Ask me about FSSAI registration or food labelling, and I’ll keep the answer tied to the source documents. When the corpus cannot support an answer, I’ll say so.',
  },
]

function App() {
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  const [input, setInput] = useState('')
  const [sourceList, setSourceList] = useState<Source[]>([])
  const [activeSource, setActiveSource] = useState<Source | null>(null)
  const [isEvidenceOpen, setIsEvidenceOpen] = useState(false)
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const [isThinking, setIsThinking] = useState(false)

  const askQuestion = async (question: string) => {
    const trimmedQuestion = question.trim()
    if (!trimmedQuestion || isThinking) return

    setMessages((current) => [
      ...current,
      { id: Date.now(), role: 'user', text: trimmedQuestion },
    ])
    setInput('')
    setIsThinking(true)
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'}/api/questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: trimmedQuestion, retrieval_strategy: 'naive' }),
      })
      if (!response.ok) throw new Error('Request failed')
      const result = await response.json() as { answer: string; answer_type: Message['answerType']; sources: Source[] }
      setSourceList(result.sources)
      setActiveSource(result.sources[0] ?? null)
      setMessages((current) => [
        ...current,
        {
          id: Date.now() + 1,
          role: 'assistant',
          text: result.answer,
          sources: result.sources,
          answerType: result.answer_type,
        },
      ])
    } catch {
      setMessages((current) => [...current, { id: Date.now() + 1, role: 'assistant', text: 'The regulatory service is unavailable right now. Please try again in a moment.', answerType: 'abstain' }])
    } finally {
      setIsThinking(false)
    }
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    askQuestion(input)
  }

  return (
    <div className="app-shell">
      <aside className={`history-rail ${isHistoryOpen ? 'is-open' : ''}`}>
        <div className="rail-brand">
          <div className="brand-mark"><Leaf size={18} strokeWidth={2.5} /></div>
          <span>shuruwat</span>
          <button className="icon-button mobile-close" onClick={() => setIsHistoryOpen(false)} aria-label="Close conversation history"><X size={18} /></button>
        </div>
        <button className="new-chat-button" onClick={() => { setMessages(initialMessages); setSourceList([]); setActiveSource(null) }}><Plus size={17} /> New question</button>
        <div className="rail-label"><History size={14} /> Recent questions</div>
        <button className="history-item active"><span>FSSAI registration for a home business</span><ChevronRight size={15} /></button>
        <button className="history-item"><span>Ingredient list requirements</span><ChevronRight size={15} /></button>
        <button className="history-item"><span>Small package exemptions</span><ChevronRight size={15} /></button>
        <div className="rail-footer"><ShieldCheck size={15} /> Sources are curated and traceable</div>
      </aside>

      {(isHistoryOpen || isEvidenceOpen) && <button className="mobile-scrim" onClick={() => { setIsHistoryOpen(false); setIsEvidenceOpen(false) }} aria-label="Close panels" />}

      <main className="main-column">
        <header className="topbar">
          <button className="icon-button mobile-menu" onClick={() => setIsHistoryOpen(true)} aria-label="Open conversation history"><Menu size={20} /></button>
          <div className="topbar-title"><span>Regulatory copilot</span><span className="status-dot" /> <small>FSSAI corpus</small></div>
          <button className="scope-button"><CircleHelp size={16} /> Scope</button>
        </header>

        <section className="chat-area">
          <div className="eyebrow"><Sparkles size={15} /> Grounded guidance for your first food venture</div>
          <div className="thread">
            {messages.map((message) => (
              <article className={`message ${message.role}`} key={message.id}>
                {message.role === 'assistant' && <div className="assistant-avatar"><Leaf size={16} /></div>}
                <div className="message-content">
                  <div className="message-meta">{message.role === 'assistant' ? 'Shuruwat' : 'You'} <span>{message.role === 'assistant' ? '· source-backed' : ''}</span></div>
                  <p className={message.answerType === 'abstain' || message.answerType === 'hand_off' ? 'answer-boundary' : ''}>{message.text}</p>
                  {message.sources && <div className="citation-row">
                    {message.sources.map((source) => <button className="citation" key={source.id} onClick={() => { setActiveSource(source); setIsEvidenceOpen(true) }}><FileText size={13} /> {source.id}</button>)}
                  </div>}
                </div>
              </article>
            ))}
            {isThinking && <div className="thinking"><div className="assistant-avatar"><Leaf size={16} /></div><span className="thinking-dots"><i /><i /><i /></span><span>Checking the corpus</span></div>}
          </div>

          {messages.length === 1 && <div className="starter-grid">
            <span className="starter-label">Start with a question</span>
            {starterQuestions.map((question) => <button key={question} className="starter-card" onClick={() => askQuestion(question)}><span>{question}</span><ArrowUp size={15} /></button>)}
          </div>}

          <form className="composer" onSubmit={handleSubmit}>
            <textarea value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask about FSSAI registration or food labelling..." rows={2} aria-label="Your regulatory question" />
            <div className="composer-footer"><span><Search size={14} /> English sources · Naive retrieval</span><button className="send-button" type="submit" disabled={!input.trim() || isThinking} aria-label="Send question"><ArrowUp size={19} /></button></div>
          </form>
          <p className="disclaimer">Shuruwat provides information based on its curated FSSAI sources and is not legal advice. Verify requirements with FSSAI or a qualified professional before acting.</p>
        </section>
      </main>

      <aside className={`evidence-panel ${isEvidenceOpen ? 'is-open' : ''}`}>
        <div className="evidence-header"><div><span className="panel-kicker">Evidence</span><h2>Source trail</h2></div><button className="icon-button mobile-close" onClick={() => setIsEvidenceOpen(false)} aria-label="Close evidence panel"><X size={18} /></button></div>
        <div className="evidence-intro"><BookOpen size={17} /><span>Every material claim should lead back to a document, section, and page.</span></div>
        {sourceList.length === 0 ? <div className="empty-evidence">Sources will appear here when an answer is grounded in the corpus.</div> : sourceList.map((source) => <button className={`source-card ${activeSource?.id === source.id ? 'selected' : ''}`} key={source.id} onClick={() => setActiveSource(source)}><div className="source-topline"><span>{source.id}</span><span>p. {source.page}</span></div><h3>{source.section ?? 'Section not labelled'}</h3><p>{source.title} · {source.authority}</p><div className="source-excerpt">“{source.excerpt}”</div></button>)}
        <div className="panel-note"><ShieldCheck size={16} /><div><strong>Evidence first</strong><p>If the sources don’t cover your question, Shuruwat will abstain instead of guessing.</p></div></div>
      </aside>
    </div>
  )
}

export default App
