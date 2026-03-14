/**
 * Audio capture and playback for Voice AI Agent.
 * Handles microphone input (PCM 16kHz 16-bit) and audio output.
 */

export class AudioCapture {
  private stream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private isRecording = false;
  private onAudioData: ((data: ArrayBuffer) => void) | null = null;

  async start(onAudioData: (data: ArrayBuffer) => void): Promise<void> {
    this.onAudioData = onAudioData;

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      this.audioContext = new AudioContext({ sampleRate: 16000 });
      this.source = this.audioContext.createMediaStreamSource(this.stream);

      // ScriptProcessor for raw PCM access (deprecated but widely supported)
      this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);
      this.processor.onaudioprocess = (event) => {
        if (!this.isRecording) return;

        const input = event.inputBuffer.getChannelData(0);
        // Convert float32 to int16
        const pcm16 = new Int16Array(input.length);
        for (let i = 0; i < input.length; i++) {
          const s = Math.max(-1, Math.min(1, input[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }

        this.onAudioData?.(pcm16.buffer);
      };

      this.source.connect(this.processor);
      this.processor.connect(this.audioContext.destination);
      this.isRecording = true;
    } catch (err) {
      console.error('Failed to start audio capture:', err);
      throw err;
    }
  }

  stop(): void {
    this.isRecording = false;

    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }
    if (this.source) {
      this.source.disconnect();
      this.source = null;
    }
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
  }

  get recording(): boolean {
    return this.isRecording;
  }
}


export class AudioPlayer {
  private audioContext: AudioContext | null = null;
  private queue: AudioBuffer[] = [];
  private isPlaying = false;
  private currentSource: AudioBufferSourceNode | null = null;

  constructor() {
    this.audioContext = new AudioContext({ sampleRate: 16000 });
  }

  async playChunk(pcmData: ArrayBuffer): Promise<void> {
    if (!this.audioContext) return;

    // Convert PCM 16-bit to Float32
    const int16 = new Int16Array(pcmData);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768;
    }

    const buffer = this.audioContext.createBuffer(1, float32.length, 16000);
    buffer.copyToChannel(float32, 0);
    this.queue.push(buffer);

    if (!this.isPlaying) {
      this.playNext();
    }
  }

  private playNext(): void {
    if (!this.audioContext || this.queue.length === 0) {
      this.isPlaying = false;
      return;
    }

    this.isPlaying = true;
    const buffer = this.queue.shift()!;
    const source = this.audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(this.audioContext.destination);
    source.onended = () => this.playNext();
    source.start();
    this.currentSource = source;
  }

  cancel(): void {
    this.queue = [];
    if (this.currentSource) {
      try {
        this.currentSource.stop();
      } catch {}
      this.currentSource = null;
    }
    this.isPlaying = false;
  }
}
