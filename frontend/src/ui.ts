/**
 * UI controller for Voice AI Agent.
 * Manages transcript display, latency panel, reasoning traces, and campaigns.
 */

export class UIController {
  private transcriptContainer: HTMLElement;
  private reasoningContainer: HTMLElement;

  constructor() {
    this.transcriptContainer = document.getElementById('transcript-messages')!;
    this.reasoningContainer = document.getElementById('reasoning-traces')!;
    this.setupTogglePanels();
  }

  // ── Connection Status ──
  setConnectionStatus(connected: boolean): void {
    const badge = document.getElementById('connection-status')!;
    badge.textContent = connected ? 'Connected' : 'Disconnected';
    badge.className = `status-badge ${connected ? 'connected' : 'disconnected'}`;
  }

  // ── Transcript ──
  addMessage(role: 'user' | 'assistant', text: string): void {
    const msg = document.createElement('div');
    msg.className = `message ${role}`;

    const label = document.createElement('div');
    label.className = 'message-label';
    label.textContent = role === 'user' ? '🗣 You' : '🤖 Agent';

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.textContent = text;

    msg.appendChild(label);
    msg.appendChild(bubble);
    this.transcriptContainer.appendChild(msg);

    // Auto-scroll
    const container = document.getElementById('transcript-container')!;
    container.scrollTop = container.scrollHeight;
  }

  // ── Latency ──
  updateLatency(breakdown: any): void {
    const total = breakdown.total_ms || 0;
    const checkpoints = breakdown.checkpoints || {};

    this.setLatencyValue('latency-total', total, 'ms');
    this.setLatencyValue('latency-stt', checkpoints.stt_ms, 'ms');
    this.setLatencyValue('latency-llm', checkpoints.llm_ms, 'ms');
    this.setLatencyValue('latency-tts', checkpoints.tts_ms, 'ms');
  }

  private setLatencyValue(id: string, value: number | undefined, unit: string): void {
    const el = document.getElementById(id);
    if (!el) return;

    if (value === undefined) {
      el.textContent = '—';
      el.className = 'value';
      return;
    }

    el.textContent = `${Math.round(value)}${unit}`;
    el.className = 'value';

    if (value > 450) el.classList.add('danger');
    else if (value > 300) el.classList.add('warn');
  }

  // ── Reasoning Traces ──
  updateReasoningTraces(traces: any[]): void {
    this.reasoningContainer.innerHTML = '';

    for (const trace of traces) {
      const entry = document.createElement('div');
      entry.className = 'trace-entry';

      const header = document.createElement('div');
      header.innerHTML = `
        <span class="trace-step">${trace.step}</span>
        <span class="trace-time">+${trace.elapsed_ms}ms</span>
      `;

      entry.appendChild(header);

      if (trace.data) {
        const dataEl = document.createElement('div');
        dataEl.className = 'trace-data';
        dataEl.textContent = JSON.stringify(trace.data, null, 0).slice(0, 200);
        entry.appendChild(dataEl);
      }

      this.reasoningContainer.appendChild(entry);
    }

    // Scroll to bottom
    this.reasoningContainer.scrollTop = this.reasoningContainer.scrollHeight;
  }

  // ── Recording State ──
  setRecording(isRecording: boolean): void {
    const micBtn = document.getElementById('mic-button')!;
    const indicator = document.getElementById('recording-indicator')!;

    if (isRecording) {
      micBtn.classList.add('recording');
      indicator.classList.remove('hidden');
    } else {
      micBtn.classList.remove('recording');
      indicator.classList.add('hidden');
    }
  }

  // ── Panel Toggles ──
  private setupTogglePanels(): void {
    document.querySelectorAll('.panel-title[data-toggle]').forEach((title) => {
      title.addEventListener('click', () => {
        const targetId = (title as HTMLElement).dataset.toggle!;
        const content = document.getElementById(targetId);
        if (content) {
          content.classList.toggle('hidden');
          title.classList.toggle('collapsed');
        }
      });
    });
  }
}
