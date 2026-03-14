/**
 * Voice AI Agent — Frontend Entry Point
 *
 * Wires up WebSocket, audio capture/playback, and UI.
 */

import './styles.css';
import { VoiceWebSocket } from './websocket';
import { AudioCapture, AudioPlayer } from './audio';
import { UIController } from './ui';

// ── Initialise ──
const ws = new VoiceWebSocket();
const audioCapture = new AudioCapture();
const audioPlayer = new AudioPlayer();
const ui = new UIController();

let currentSessionId = '';
let isRecording = false;

// ── API Helpers ──
async function startSession(): Promise<string> {
  const resp = await fetch('/api/session/start', { method: 'POST' });
  const data = await resp.json();
  return data.session_id;
}

// ── Connect ──
async function connect(): Promise<void> {
  try {
    currentSessionId = await startSession();
    await ws.connect(currentSessionId);
  } catch (err) {
    console.error('Connection failed:', err);
    ui.addMessage('assistant', 'Connection failed. Please refresh the page.');
  }
}

// ── WebSocket Event Handlers ──
ws.on('connected', () => {
  ui.setConnectionStatus(true);
  console.log('Connected to voice session:', currentSessionId);
});

ws.on('disconnected', () => {
  ui.setConnectionStatus(false);
});

ws.on('transcript', (msg: any) => {
  if (msg.is_final && msg.text) {
    ui.addMessage(msg.role, msg.text);
  }
});

ws.on('audio', (buffer: ArrayBuffer) => {
  audioPlayer.playChunk(buffer);
});

ws.on('reasoning', (msg: any) => {
  if (msg.traces) {
    ui.updateReasoningTraces(msg.traces);
  }
});

ws.on('latency', (msg: any) => {
  if (msg.breakdown) {
    ui.updateLatency(msg.breakdown);
  }
});

ws.on('error', (err: any) => {
  console.error('WebSocket error:', err);
});

// ── Mic Button ──
const micButton = document.getElementById('mic-button')!;

micButton.addEventListener('mousedown', async () => {
  if (!ws.isConnected) {
    await connect();
  }

  if (!isRecording) {
    try {
      await audioCapture.start((data) => {
        ws.sendAudio(data);
      });
      isRecording = true;
      ui.setRecording(true);

      // Cancel any playing audio (barge-in)
      audioPlayer.cancel();
      ws.sendControl('barge_in');
    } catch (err) {
      console.error('Mic start failed:', err);
    }
  }
});

micButton.addEventListener('mouseup', () => {
  if (isRecording) {
    audioCapture.stop();
    isRecording = false;
    ui.setRecording(false);
  }
});

micButton.addEventListener('mouseleave', () => {
  if (isRecording) {
    audioCapture.stop();
    isRecording = false;
    ui.setRecording(false);
  }
});

// ── Text Input ──
const textInput = document.getElementById('text-input') as HTMLInputElement;
const sendButton = document.getElementById('send-button')!;

async function sendTextMessage(): Promise<void> {
  const text = textInput.value.trim();
  if (!text) return;

  if (!ws.isConnected) {
    await connect();
  }

  ws.sendText(text);
  textInput.value = '';
}

sendButton.addEventListener('click', sendTextMessage);

textInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    sendTextMessage();
  }
});

// ── Language Selector ──
const languageSelect = document.getElementById('language-select') as HTMLSelectElement;

languageSelect.addEventListener('change', () => {
  const lang = languageSelect.value;
  if (ws.isConnected) {
    ws.sendControl('set_language', { language: lang });
  }
});

// ── Campaign Trigger ──
const campaignBtn = document.getElementById('trigger-campaign')!;
const campaignStatus = document.getElementById('campaign-status')!;

campaignBtn.addEventListener('click', async () => {
  try {
    const resp = await fetch('/api/campaigns/trigger?campaign_id=demo', {
      method: 'POST',
    });
    const data = await resp.json();
    campaignStatus.textContent = `Campaign ${data.campaign_id}: ${data.status}`;
    campaignStatus.classList.remove('empty-state');
  } catch (err) {
    campaignStatus.textContent = 'Failed to trigger campaign';
  }
});

// ── Auto-connect on load ──
connect();
